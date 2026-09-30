"""
Servidor web simple para servir el frontend CDTO
"""

import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"


class CDTOFrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        # Agregar headers CORS
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_GET(self):
        # Servir index.html para rutas no encontradas
        target_path = FRONTEND_DIR / self.path.lstrip("/")
        if self.path == "/" or not target_path.is_file():
            self.path = "/index.html"
        return super().do_GET()


if __name__ == "__main__":
    PORT = 3000
    host = "0.0.0.0"

    if not FRONTEND_DIR.exists():
        print(f"\n❌ No se encontró el frontend en: {FRONTEND_DIR}")
        sys.exit(1)

    server_address = (host, PORT)
    httpd = HTTPServer(server_address, CDTOFrontendHandler)

    print("\n" + "=" * 60)
    print("  CDTO Frontend Web Server")
    print("=" * 60)
    print(f"\n✅ Servidor iniciado en: http://localhost:{PORT}")
    print(f"📍 Sirviendo desde: {FRONTEND_DIR}")
    print(f"\n🌐 Abre en tu navegador: http://localhost:{PORT}")
    print("\n⏹️  Presiona Ctrl+C para detener el servidor\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n⏹️  Servidor detenido")
        sys.exit(0)
