package com.androidtv.fetch.gateway;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** A one-request-per-connection HTTP/1.1 server for tests; Android's test classpath has no JDK httpserver. */
final class TinyHttpServer implements AutoCloseable {

    /** One request as received. */
    static final class Request {
        final String method;
        final String target;
        final Map<String, String> headers;
        final String body;

        Request(String method, String target, Map<String, String> headers, String body) {
            this.method = method;
            this.target = target;
            this.headers = headers;
            this.body = body;
        }
    }

    final List<Request> requests = new ArrayList<>();
    volatile int status = 200;
    volatile String reply = "{}";
    volatile String location = "";

    private final ServerSocket socket;
    private final Thread thread;

    TinyHttpServer() throws IOException {
        socket = new ServerSocket(0, 10, InetAddress.getLoopbackAddress());
        thread = new Thread(this::serve, "tiny-http");
        thread.setDaemon(true);
        thread.start();
    }

    String url() {
        return "http://127.0.0.1:" + socket.getLocalPort() + "/";
    }

    private void serve() {
        while (!socket.isClosed()) {
            try (Socket client = socket.accept()) {
                handle(client);
            } catch (IOException e) {
                return;
            }
        }
    }

    private void handle(Socket client) throws IOException {
        BufferedReader in = new BufferedReader(new InputStreamReader(client.getInputStream(), StandardCharsets.UTF_8));
        String[] requestLine = in.readLine().split(" ");
        Map<String, String> headers = new HashMap<>();
        for (String line = in.readLine(); line != null && !line.isEmpty(); line = in.readLine()) {
            int colon = line.indexOf(':');
            headers.put(line.substring(0, colon).trim().toLowerCase(Locale.ROOT), line.substring(colon + 1).trim());
        }
        char[] body = new char[Integer.parseInt(headers.getOrDefault("content-length", "0"))];
        int read = 0;
        while (read < body.length) read += in.read(body, read, body.length - read);
        synchronized (requests) {
            requests.add(new Request(requestLine[0], requestLine[1], headers, new String(body)));
        }
        byte[] payload = reply.getBytes(StandardCharsets.UTF_8);
        String head = "HTTP/1.1 " + status + " X\r\nContent-Type: application/json\r\nContent-Length: " + payload.length
                + (location.isEmpty() ? "" : "\r\nLocation: " + location) + "\r\nConnection: close\r\n\r\n";
        OutputStream out = client.getOutputStream();
        out.write(head.getBytes(StandardCharsets.UTF_8));
        out.write(payload);
        out.flush();
    }

    @Override
    public void close() throws IOException {
        socket.close();
    }
}
