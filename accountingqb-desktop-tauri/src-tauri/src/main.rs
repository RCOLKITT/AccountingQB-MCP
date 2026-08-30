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
use tauri_plugin_updater::UpdaterExt;

const APP_VERSION: &str = env!("CARGO_PKG_VERSION");

struct Sidecar(Mutex<Option<Child>>);

fn free_port() -> u16 {
    for p in [4318u16, 4319, 4320] {  // 4318 = the port the Coffer/Hearth contract expects
        if TcpListener::bind(("127.0.0.1", p)).is_ok() {
            return p;
        }
    }
    TcpListener::bind(("127.0.0.1", 0))
        .map(|l| l.local_addr().unwrap().port())
        .unwrap_or(4318)
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
        .env("ACCOUNTINGQB_APP_VERSION", APP_VERSION) // sidecar serves "What's new" for this version
        .spawn()
        .expect("failed to start the AccountingQB server sidecar");

    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Sidecar(Mutex::new(Some(child))))
        .setup(move |app| {
            wait_healthy(port); // window opens regardless; the server may finish booting
            // Pass the running version to the UI so it can show a one-time "What's new" panel.
            let url = format!("http://127.0.0.1:{}/?in_app=1&v={}", port, APP_VERSION);
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url.parse().unwrap()))
                .title("AccountingQB")
                .inner_size(1360.0, 900.0)
                .min_inner_size(900.0, 600.0)
                .build()?;
            // Auto-update: check GitHub for a newer signed build; if found, download, install,
            // and relaunch into it. Silent + non-blocking — the window is already up. The
            // signature is verified against the pinned pubkey (tauri.conf.json) before install.
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let updater = match handle.updater() {
                    Ok(u) => u,
                    Err(e) => { eprintln!("[updater] unavailable: {e}"); return; }
                };
                match updater.check().await {
                    Ok(Some(update)) => {
                        eprintln!("[updater] {} available (have {APP_VERSION}); downloading…", update.version);
                        match update.download_and_install(|_, _| {}, || {}).await {
                            Ok(_) => { eprintln!("[updater] installed; relaunching"); handle.restart(); }
                            Err(e) => eprintln!("[updater] install failed: {e}"),
                        }
                    }
                    Ok(None) => eprintln!("[updater] up to date ({APP_VERSION})"),
                    Err(e) => eprintln!("[updater] check failed: {e}"),
                }
            });
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
