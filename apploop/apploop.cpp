// Pomocnik do łapania dźwięku z jednej aplikacji (WASAPI process loopback, Windows 10 2004+).
//   apploop list          -> wiersze "pid<TAB>nazwa.exe<TAB>0|1" (1 = teraz gra) dla programów z sesją audio
//   apploop capture <pid> -> surowe PCM 48000 Hz, 2 kanały, int16 na stdout (do końca procesu docelowego)
// Kompilacja (msys64 ucrt64): g++ -O2 -static apploop.cpp -o ../pc/apploop.exe -lole32 -lmmdevapi -luuid
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audiopolicy.h>
#include <fcntl.h>
#include <io.h>
#include <cstdio>
#include <cstdlib>
#include <set>
#include <string>

// z audioclientactivationparams.h (brak w MinGW)
enum AUDIOCLIENT_ACTIVATION_TYPE { ACT_DEFAULT = 0, ACT_PROCESS_LOOPBACK = 1 };
enum PROCESS_LOOPBACK_MODE { INCLUDE_TARGET_PROCESS_TREE = 0, EXCLUDE_TARGET_PROCESS_TREE = 1 };
struct AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS { DWORD TargetProcessId; PROCESS_LOOPBACK_MODE ProcessLoopbackMode; };
struct AUDIOCLIENT_ACTIVATION_PARAMS {
    AUDIOCLIENT_ACTIVATION_TYPE ActivationType;
    AUDIOCLIENT_PROCESS_LOOPBACK_PARAMS ProcessLoopbackParams;
};
DEFINE_GUID(IID_IAgileObject_, 0x94ea2b94, 0xe9cc, 0x49e0, 0xc0, 0xff, 0xee, 0x64, 0xca, 0x8f, 0x5b, 0x90);

static std::string nazwa_procesu(DWORD pid) {
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!h) return "";
    wchar_t sciezka[MAX_PATH];
    DWORD n = MAX_PATH;
    std::string wynik;
    if (QueryFullProcessImageNameW(h, 0, sciezka, &n)) {
        const wchar_t *plik = wcsrchr(sciezka, L'\\');
        plik = plik ? plik + 1 : sciezka;
        char utf8[MAX_PATH * 3];
        WideCharToMultiByte(CP_UTF8, 0, plik, -1, utf8, sizeof utf8, nullptr, nullptr);
        wynik = utf8;
    }
    CloseHandle(h);
    return wynik;
}

static int lista() {
    IMMDeviceEnumerator *en = nullptr;
    if (FAILED(CoCreateInstance(CLSID_MMDeviceEnumerator, nullptr, CLSCTX_ALL, IID_IMMDeviceEnumerator, (void **)&en)))
        return 1;
    IMMDeviceCollection *urz = nullptr;
    en->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &urz);
    UINT ile = 0;
    urz->GetCount(&ile);
    std::set<DWORD> byly;
    for (UINT d = 0; d < ile; d++) {
        IMMDevice *dev = nullptr;
        IAudioSessionManager2 *mgr = nullptr;
        IAudioSessionEnumerator *sesje = nullptr;
        if (FAILED(urz->Item(d, &dev)) ||
            FAILED(dev->Activate(IID_IAudioSessionManager2, CLSCTX_ALL, nullptr, (void **)&mgr)) ||
            FAILED(mgr->GetSessionEnumerator(&sesje)))
            continue;
        int n = 0;
        sesje->GetCount(&n);
        for (int i = 0; i < n; i++) {
            IAudioSessionControl *s = nullptr;
            IAudioSessionControl2 *s2 = nullptr;
            if (FAILED(sesje->GetSession(i, &s)) ||
                FAILED(s->QueryInterface(IID_IAudioSessionControl2, (void **)&s2)))
                continue;
            DWORD pid = 0;
            AudioSessionState st;
            s2->GetProcessId(&pid);
            s2->GetState(&st);
            std::string nazwa = pid ? nazwa_procesu(pid) : "";
            if (!nazwa.empty() && byly.insert(pid).second)
                printf("%lu\t%s\t%d\n", pid, nazwa.c_str(), st == AudioSessionStateActive);
            s2->Release();
            s->Release();
        }
        sesje->Release();
        mgr->Release();
        dev->Release();
    }
    return 0;
}

// ActivateAudioInterfaceAsync woła ten obiekt z innego wątku - musi być „agile”
struct Handler : IActivateAudioInterfaceCompletionHandler {
    HANDLE gotowe = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    LONG ref = 1;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void **out) override {
        if (iid == IID_IUnknown || iid == IID_IActivateAudioInterfaceCompletionHandler || iid == IID_IAgileObject_) {
            *out = this;
            AddRef();
            return S_OK;
        }
        *out = nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&ref); }
    ULONG STDMETHODCALLTYPE Release() override { return InterlockedDecrement(&ref); }
    HRESULT STDMETHODCALLTYPE ActivateCompleted(IActivateAudioInterfaceAsyncOperation *) override {
        SetEvent(gotowe);
        return S_OK;
    }
};

static int przechwyc(DWORD pid) {
    HANDLE cel = OpenProcess(SYNCHRONIZE, FALSE, pid);
    if (!cel) { fprintf(stderr, "no such process %lu\n", pid); return 2; }

    AUDIOCLIENT_ACTIVATION_PARAMS ap = {};
    ap.ActivationType = ACT_PROCESS_LOOPBACK;
    ap.ProcessLoopbackParams = {pid, INCLUDE_TARGET_PROCESS_TREE};
    PROPVARIANT pv = {};
    pv.vt = VT_BLOB;
    pv.blob.cbSize = sizeof ap;
    pv.blob.pBlobData = (BYTE *)&ap;

    Handler h;
    IActivateAudioInterfaceAsyncOperation *op = nullptr;
    HRESULT hr = ActivateAudioInterfaceAsync(L"VAD\\Process_Loopback", IID_IAudioClient, &pv, &h, &op);
    if (FAILED(hr)) { fprintf(stderr, "ActivateAudioInterfaceAsync 0x%08lx\n", hr); return 3; }
    WaitForSingleObject(h.gotowe, INFINITE);
    HRESULT wynik;
    IUnknown *unk = nullptr;
    op->GetActivateResult(&wynik, &unk);
    if (FAILED(wynik)) { fprintf(stderr, "aktywacja 0x%08lx\n", wynik); return 3; }
    IAudioClient *klient = nullptr;
    unk->QueryInterface(IID_IAudioClient, (void **)&klient);

    WAVEFORMATEX wf = {WAVE_FORMAT_PCM, 2, 48000, 48000 * 4, 4, 16, 0};
    hr = klient->Initialize(AUDCLNT_SHAREMODE_SHARED,
                            AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK |
                                AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM,
                            200000, 0, &wf, nullptr);
    if (FAILED(hr)) { fprintf(stderr, "Initialize 0x%08lx\n", hr); return 4; }
    HANDLE ev = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    klient->SetEventHandle(ev);
    IAudioCaptureClient *cap = nullptr;
    klient->GetService(IID_IAudioCaptureClient, (void **)&cap);
    klient->Start();

    _setmode(_fileno(stdout), _O_BINARY);
    static BYTE cisza[48000 * 4];
    while (WaitForSingleObject(cel, 0) == WAIT_TIMEOUT) {
        WaitForSingleObject(ev, 200);
        UINT32 n = 0;
        while (SUCCEEDED(cap->GetNextPacketSize(&n)) && n) {
            BYTE *dane;
            UINT32 ramki;
            DWORD flagi;
            if (FAILED(cap->GetBuffer(&dane, &ramki, &flagi, nullptr, nullptr))) break;
            const BYTE *src = (flagi & AUDCLNT_BUFFERFLAGS_SILENT) ? cisza : dane;
            bool ok = fwrite(src, 4, ramki, stdout) == ramki;
            cap->ReleaseBuffer(ramki);
            if (!ok || fflush(stdout)) return 0;      // Python się zamknął
        }
    }
    klient->Stop();
    return 0;
}

int main(int argc, char **argv) {
    CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (argc >= 2 && !strcmp(argv[1], "list")) return lista();
    if (argc >= 3 && !strcmp(argv[1], "capture")) return przechwyc(strtoul(argv[2], nullptr, 10));
    fprintf(stderr, "usage: apploop list | apploop capture <pid>\n");
    return 1;
}
