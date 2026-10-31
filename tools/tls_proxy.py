"""Stands in for Whatbox's HTTPS proxy in tests: TLS on the LAN, plain TCP to the gateway on loopback.

Usage: python3 tools/tls_proxy.py <listen-port> <gateway-port>
"""
import asyncio
import ssl
import sys
from pathlib import Path

TLS_DIR = Path(__file__).resolve().parents[1] / ".local" / "tls"


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, ssl.SSLError):
        pass
    finally:
        writer.close()


async def forward(client_reader, client_writer, gateway_port: int) -> None:
    try:
        gateway_reader, gateway_writer = await asyncio.open_connection("127.0.0.1", gateway_port)
    except OSError:
        client_writer.close()
        return
    await asyncio.gather(pipe(client_reader, gateway_writer), pipe(gateway_reader, client_writer))


async def main(listen_port: int, gateway_port: int) -> None:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(TLS_DIR / "server.pem", TLS_DIR / "server.key")
    server = await asyncio.start_server(lambda r, w: forward(r, w, gateway_port), "0.0.0.0", listen_port, ssl=context)
    print(f"TLS {listen_port} -> 127.0.0.1:{gateway_port}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), int(sys.argv[2])))
