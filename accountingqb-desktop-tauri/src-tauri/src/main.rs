// AccountingQB desktop shell (Tauri v2) — Door 2.
//
// Spawns the bundled PyInstaller server sidecar (accountingqb-local + connector in one
// binary, no Python required on the user's machine), waits for /healthz, then opens the
// window straight onto the local server so the page origin IS the server (no CORS, the
// artifact runs unmodified). Kills the child on exit. Ported from Hearth's main.rs;
// env var names match accountingqb-local/serve.py.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

struct Sidecar(Mutex<Option<Child>>);

fn free_port() -> u16 {
    for p in [8788u16, 8789, 8790] {
        if TcpListener::bind(("127.0.0.1", p)).is_ok() {
            return p;
        }
    }
    TcpListener::bind(("127.0.0.1", 0))
        .map(|l| l.local_addr().unwrap().port())
        .unwrap_or(8788)
}

fn sidecar_path() -> std::path::PathBuf {
    let exe = std::env::current_exe().expect("current_exe");
    let dir = exe.parent().expect("exe dir");
    let name = if cfg!(windows) { "accountingqb-server.exe" } else { "accountingqb-server" };
    let bundled = dir.join(name);
    if bundled.exists() {
        return bundled;
    }
    // `tauri dev` fallback: the target-triple name under src-tauri/binaries.
    let triple = tauri::utils::platform::target_triple().unwrap_or_default();
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("binaries")
        .join(format!("accountingqb-server-{}{}", triple, if cfg!(windows) { ".exe" } else { "" }))
}

fn wait_healthy(port: u16) -> bool {
    let deadline = Instant::now() + Duration::from_secs(90);
    while Instant::now() < deadline {
        if let Ok(mut s) = std::net::TcpStream::connect(("127.0.0.1", port)) {
            use std::io::{Read, Write};
            let _ = s.write_all(
                format!("GET /healthz HTTP/1.0\r\nHost: 127.0.0.1:{}\r\n\r\n", port).as_bytes(),
            );
            let mut buf = String::new();
            let _ = s.read_to_string(&mut buf);
            if buf.contains("200") {
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    false
}

fn home_dir() -> std::path::PathBuf {
    std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::path::PathBuf::from("."))
}

fn main() {
    let port = free_port();
    let data_dir = home_dir().join(".accountingqb");

    let child = Command::new(sidecar_path())
        .env("ACCOUNTINGQB_PORT", port.to_string())
        .env("ACCOUNTINGQB_NO_OPEN", "1")
        .env("ACCOUNTINGQB_DATA_DIR", &data_dir)
        .spawn()
        .expect("failed to start the AccountingQB server sidecar");

    tauri::Builder::default()
        .manage(Sidecar(Mutex::new(Some(child))))
        .setup(move |app| {
            wait_healthy(port); // window opens regardless; the server may finish booting
            let url = format!("http://127.0.0.1:{}/?in_app=1", port);
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url.parse().unwrap()))
                .title("AccountingQB")
                .inner_size(1360.0, 900.0)
                .min_inner_size(900.0, 600.0)
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building AccountingQB")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app.try_state::<Sidecar>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut c) = guard.take() {
                            let _ = c.kill();
                        }
                    }
                }
            }
        });
}
