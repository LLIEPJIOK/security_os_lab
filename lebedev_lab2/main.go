package main

import (
	"context"
	"errors"
	"fmt"
	"html/template"
	"io"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"slices"
	"strings"
	"syscall"
	"time"
)

const (
	tempFileNameTemplate = "secret-build-*.cpp"
	secretTemplate       = `
#include <windows.h>

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg)
    {
        case WM_DESTROY:
        case WM_CLOSE:
            PostQuitMessage(0);
            return 0;
        default:
            return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR, int nCmdShow)
{
    const wchar_t* secret = L"{{.Secret}}";

    // Регистрируем простой класс окна
    WNDCLASSW wc = {};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = L"SecretWindowClass";
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);

    RegisterClassW(&wc);

    HWND hwnd = CreateWindowExW(
        0,
        wc.lpszClassName,
        L"Secret",
        WS_OVERLAPPEDWINDOW | WS_VISIBLE,
        CW_USEDEFAULT, CW_USEDEFAULT, 600, 500,
        NULL, NULL, hInstance, NULL
    );

    HWND hEdit = CreateWindowExW(
        0, L"EDIT", secret,
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
        10, 10, 570, 440,
        hwnd, NULL, hInstance, NULL
    );

    HFONT hFont = CreateFontW(
        18, 0, 0, 0,
        FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,
        VARIABLE_PITCH,
        L"Segoe UI"
    );
    SendMessageW(hEdit, WM_SETFONT, (WPARAM)hFont, TRUE);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0))
    {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    DeleteObject(hFont);
    return 0;
}
`
	secretHTML = `
<html>
<head>
  <style>
    body {
      font-family: sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      background-color: #f8f9fa;
    }
    form {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      width: 100%;
      max-width: 600px;
    }
    textarea {
      width: 100%;
      height: 300px;
      font-size: 16px;
      padding: 10px;
      resize: vertical;
    }
    button {
      padding: 8px 16px;
      font-size: 16px;
      cursor: pointer;
      border: none;
      border-radius: 6px;
      background-color: #007bff;
      color: white;
      transition: background-color 0.3s;
    }
    button:hover {
      background-color: #0056b3;
    }
  </style>
</head>
<body>
  <h2>Создать программу с секретом</h2>
  <form method="POST" action="/build">
    <textarea name="secret" placeholder="Введите секрет..."></textarea>
    <button type="submit">Создать</button>
  </form>
</body>
</html>
`
)

func escapeForCppWideWithNewlines(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	s = strings.ReplaceAll(s, `"`, `\"`)
	s = strings.ReplaceAll(s, "\r\n", `\r\n`)
	s = strings.ReplaceAll(s, "\n", `\r\n`)

	return s
}

type Closer = func() error

type RemoveReader struct {
	r       io.ReadCloser
	closers []Closer
}

func NewRemoveReader(path string) (*RemoveReader, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("cannot open file: %w", err)
	}

	return &RemoveReader{
		r: f,
		closers: []Closer{
			func() error {
				return os.Remove(path)
			},
			f.Close,
		},
	}, nil
}

func (rr *RemoveReader) Read(p []byte) (n int, err error) {
	return rr.r.Read(p)
}

func (rr *RemoveReader) Close() error {
	var errs []error
	for _, closer := range slices.Backward(rr.closers) {
		if err := closer(); err != nil {
			errs = append(errs, err)
		}
	}

	return errors.Join(errs...)
}

type SecretBuilder struct {
	tmpl *template.Template
}

func NewSecretBuilder() (*SecretBuilder, error) {
	tmpl, err := template.New("code").Parse(secretTemplate)
	if err != nil {
		return nil, fmt.Errorf("failed to parse template: %w", err)
	}

	return &SecretBuilder{
		tmpl: tmpl,
	}, nil
}

func (b *SecretBuilder) BuildReader(secret string) (io.ReadCloser, error) {
	f, err := os.CreateTemp("", tempFileNameTemplate)
	if err != nil {
		return nil, fmt.Errorf("failed to create temp file: %w", err)
	}

	defer func() {
		if err := f.Close(); err != nil {
			slog.Error("Failed to close temp file", slog.Any("error", err))
		}
		if err := os.Remove(f.Name()); err != nil {
			slog.Error("Failed to remove temp file", slog.Any("error", err))
		}
	}()

	if err := b.tmpl.Execute(f, map[string]any{"Secret": template.HTML(secret)}); err != nil {
		return nil, fmt.Errorf("failed to execute template: %w", err)
	}

	outFile := f.Name() + ".exe"
	cmd := exec.Command("gcc", "-mwindows", "-o", outFile, f.Name())

	out, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("build failed: %v\n%s", err, string(out))
	}

	rr, err := NewRemoveReader(outFile)
	if err != nil {
		return nil, fmt.Errorf("failed to create remove reader: %w", err)
	}

	return rr, nil
}

type Builder interface {
	BuildReader(secret string) (io.ReadCloser, error)
}

type Server struct {
	builder Builder
}

func NewServer(Builder Builder) *Server {
	return &Server{
		builder: Builder,
	}
}

func (s *Server) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/", s.Secret)
	mux.HandleFunc("/build", s.Build)
}

func (s *Server) Secret(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, secretHTML)
}

func (s *Server) Build(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	secret := escapeForCppWideWithNewlines(r.FormValue("secret"))
	if secret == "" {
		http.Error(w, "empty secret", http.StatusBadRequest)
		return
	}

	br, err := s.builder.BuildReader(secret)
	if err != nil {
		http.Error(w, fmt.Sprintf("build failed: %v", err), http.StatusInternalServerError)
		return
	}

	defer func() {
		if err := br.Close(); err != nil {
			slog.Error("Failed to close build reader", slog.Any("error", err))
		}
	}()

	w.Header().Set("Content-Disposition", "attachment; filename=\"secret.exe\"")
	w.Header().Set("Content-Type", "application/octet-stream")

	if _, err := io.Copy(w, br); err != nil {
		slog.Error("Failed to send file", slog.Any("error", err))
	}
}

func main() {
	builder, err := NewSecretBuilder()
	if err != nil {
		log.Fatal(err)
	}

	mux := http.NewServeMux()

	builderServer := NewServer(builder)
	builderServer.RegisterRoutes(mux)

	srv := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadTimeout:       5 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	go func() {
		slog.Info("Starting server", slog.String("addr", srv.Addr))

		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("Service running error", slog.Any("error", err))
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	<-stop
	slog.Info("Shutdown signal received")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("Graceful shutdown failed", slog.Any("error", err))
	} else {
		slog.Info("Server stopped gracefully")
	}
}
