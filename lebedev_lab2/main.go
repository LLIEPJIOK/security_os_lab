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
	"syscall"
	"time"
)

const (
	tempFileNameTemplate = "secret-build-*.cpp"
	secretTemplate       = `
#include <windows.h>

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int)
{
	MessageBoxW(NULL, L"{{.Secret}}", L"Secret", MB_OK);
	return 0;
}
`
	secretHTML = `
<html><body style="font-family: sans-serif">
<h2>Создать программу с секретом</h2>
<form method="POST" action="/build">
	<input name="secret" placeholder="Введите секрет" style="width:300px">
	<button type="submit">Создать</button>
</form>
</body></html>
`
)

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

	if err := b.tmpl.Execute(f, map[string]string{"Secret": secret}); err != nil {
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

	secret := r.FormValue("secret")
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
