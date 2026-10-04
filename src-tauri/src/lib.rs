use std::net::TcpListener;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

pub struct SidecarState {
    pub child: Mutex<Option<Child>>,
    pub port: u16,
}

/// Find a free ephemeral local port using OS socket assignment
pub fn find_available_port() -> u16 {
    match TcpListener::bind("127.0.0.1:0") {
        Ok(listener) => match listener.local_addr() {
            Ok(addr) => addr.port(),
            Err(_) => 8000,
        },
        Err(_) => 8000,
    }
}

/// Poll backend health endpoint until 200 OK or timeout
pub async fn wait_for_backend_health(port: u16, timeout_secs: u64) -> bool {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
        .unwrap_or_default();

    let health_url = format!("http://127.0.0.1:{}/health", port);
    let start = std::time::Instant::now();
    let max_duration = Duration::from_secs(timeout_secs);

    while start.elapsed() < max_duration {
        if let Ok(res) = client.get(&health_url).send().await {
            if res.status().is_success() {
                return true;
            }
        }
        tokio::time::sleep(Duration::from_millis(150)).await;
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = find_available_port();

    let mut sidecar_cmd = Command::new("python");
    sidecar_cmd
        .arg("apps/api/app/cli.py")
        .arg("--port")
        .arg(port.to_string())
        .arg("--host")
        .arg("127.0.0.1");

    let child = sidecar_cmd.spawn().ok();

    let state = SidecarState {
        child: Mutex::new(child),
        port,
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .manage(state)
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let port_val = port;

            tauri::async_runtime::spawn(async move {
                let is_healthy = wait_for_backend_health(port_val, 15).await;
                if is_healthy {
                    if let Some(window) = app_handle.get_webview_window("main") {
                        let script = format!(
                            "window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:{}';",
                            port_val
                        );
                        let _ = window.eval(&script);
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<SidecarState>();
                if let Ok(mut guard) = state.child.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running outlaw forge desktop application");
}
