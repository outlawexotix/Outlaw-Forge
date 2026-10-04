use std::net::TcpListener;
use std::path::Path;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

#[cfg(windows)]
pub mod job_object {
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, SetInformationJobObject,
        JobObjectExtendedLimitInformation, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    pub struct WindowsJobObjectGuard {
        job_handle: HANDLE,
    }

    impl WindowsJobObjectGuard {
        pub fn new() -> Option<Self> {
            unsafe {
                let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
                if job == 0 {
                    return None;
                }

                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

                let ok = SetInformationJobObject(
                    job,
                    JobObjectExtendedLimitInformation,
                    &info as *const _ as *const _,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                );

                if ok == 0 {
                    CloseHandle(job);
                    return None;
                }

                Some(Self { job_handle: job })
            }
        }

        pub fn assign_process(&self, child: &std::process::Child) -> bool {
            unsafe {
                let raw_handle = child.as_raw_handle() as HANDLE;
                AssignProcessToJobObject(self.job_handle, raw_handle) != 0
            }
        }
    }

    impl Drop for WindowsJobObjectGuard {
        fn drop(&mut self) {
            unsafe {
                if self.job_handle != 0 {
                    CloseHandle(self.job_handle);
                }
            }
        }
    }
}

#[cfg(not(windows))]
pub mod job_object {
    pub struct WindowsJobObjectGuard;

    impl WindowsJobObjectGuard {
        pub fn new() -> Option<Self> {
            Some(Self)
        }

        pub fn assign_process(&self, _child: &std::process::Child) -> bool {
            true
        }
    }
}

pub struct SidecarState {
    pub child: Mutex<Option<Child>>,
    pub port: u16,
    pub job_guard: Mutex<Option<job_object::WindowsJobObjectGuard>>,
}

impl SidecarState {
    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
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

/// Spawns the sidecar process (bundled executable if present, otherwise python cli)
pub fn spawn_sidecar(port: u16) -> (Option<Child>, Option<job_object::WindowsJobObjectGuard>) {
    let bundled_binary = if cfg!(windows) {
        "binaries/outlaw_forge_sidecar.exe"
    } else {
        "binaries/outlaw_forge_sidecar"
    };

    let mut cmd = if Path::new(bundled_binary).exists() {
        let mut command = Command::new(bundled_binary);
        command
            .arg("--port")
            .arg(port.to_string())
            .arg("--host")
            .arg("127.0.0.1");
        command
    } else {
        let mut command = Command::new("python");
        command
            .arg("apps/api/app/cli.py")
            .arg("--port")
            .arg(port.to_string())
            .arg("--host")
            .arg("127.0.0.1");
        command
    };

    let child = cmd.spawn().ok();

    let job_guard = job_object::WindowsJobObjectGuard::new();
    if let (Some(ref ch), Some(ref jg)) = (&child, &job_guard) {
        let _ = jg.assign_process(ch);
    }

    (child, job_guard)
}

/// Poll backend health endpoint until 200 OK or timeout with exponential backoff
pub async fn wait_for_backend_health(port: u16, timeout_secs: u64) -> bool {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
        .unwrap_or_default();

    let health_url = format!("http://127.0.0.1:{}/health", port);
    let start = std::time::Instant::now();
    let max_duration = Duration::from_secs(timeout_secs);
    let mut backoff_ms = 100u64;

    while start.elapsed() < max_duration {
        if let Ok(res) = client.get(&health_url).send().await {
            if res.status().is_success() {
                if let Ok(body) = res.json::<serde_json::Value>().await {
                    if body.get("status").and_then(|s| s.as_str()) == Some("healthy") {
                        return true;
                    }
                }
            }
        }
        tokio::time::sleep(Duration::from_millis(backoff_ms)).await;
        if backoff_ms < 300 {
            backoff_ms += 50;
        }
    }
    false
}

/// Construct native CAD menu with accelerators
pub fn build_cad_menu<R: tauri::Runtime>(app: &tauri::App<R>) -> tauri::Result<Menu<R>> {
    let file_menu = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &MenuItem::with_id(app, "menu-import", "Import 3D Model...", true, Some("Ctrl+O"))?,
            &MenuItem::with_id(app, "menu-save", "Save Project", true, Some("Ctrl+S"))?,
            &MenuItem::with_id(app, "menu-export", "Export 3MF...", true, Some("Ctrl+E"))?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "menu-exit", "Exit", true, Some("Alt+F4"))?,
        ],
    )?;

    let edit_menu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &MenuItem::with_id(app, "menu-undo", "Undo", true, Some("Ctrl+Z"))?,
            &MenuItem::with_id(app, "menu-redo", "Redo", true, Some("Ctrl+Y"))?,
        ],
    )?;

    let view_menu = Submenu::with_items(
        app,
        "View",
        true,
        &[
            &MenuItem::with_id(app, "menu-center-bed", "Center on Bed", true, Some("Ctrl+Space"))?,
            &MenuItem::with_id(app, "menu-wireframe", "Toggle Wireframe", true, Some("W"))?,
            &MenuItem::with_id(app, "menu-reset-camera", "Reset Camera", true, Some("R"))?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "menu-fullscreen", "Toggle Fullscreen", true, Some("F11"))?,
        ],
    )?;

    let help_menu = Submenu::with_items(
        app,
        "Help",
        true,
        &[
            &MenuItem::with_id(app, "menu-about", "About Outlaw Forge", true, None::<&str>)?,
        ],
    )?;

    Menu::with_items(app, &[&file_menu, &edit_menu, &view_menu, &help_menu])
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = find_available_port();
    let (child, job_guard) = spawn_sidecar(port);

    let state = SidecarState {
        child: Mutex::new(child),
        port,
        job_guard: Mutex::new(job_guard),
    };

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_fs::init())
        .manage(state)
        .setup(move |app| {
            // Build and set CAD native menu
            if let Ok(menu) = build_cad_menu(app) {
                let _ = app.set_menu(menu);
            }

            let init_script = format!(
                "window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:{}';",
                port
            );

            // Dynamic BaseURL Injection: Injects into webview via initialization_script on window creation
            // so it is available before any page JavaScript executes
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval(&init_script);
            } else {
                let _ = WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                    .title("Outlaw Forge 3D Preparation Workbench")
                    .inner_size(1440.0, 900.0)
                    .min_inner_size(1024.0, 700.0)
                    .initialization_script(&init_script)
                    .build();
            }

            let app_handle = app.handle().clone();
            let port_val = port;

            // Active Health Check Polling
            tauri::async_runtime::spawn(async move {
                let is_healthy = wait_for_backend_health(port_val, 15).await;
                if is_healthy {
                    if let Some(window) = app_handle.get_webview_window("main") {
                        let script = format!(
                            "window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:{}';",
                            port_val
                        );
                        let _ = window.eval(&script);
                        let _ = app_handle.emit("outlaw-forge:backend-ready", port_val);
                    }
                }
            });

            Ok(())
        })
        .on_menu_event(move |app_handle, event| {
            let id_str = event.id().as_ref();
            match id_str {
                "menu-import" => {
                    let _ = app_handle.emit("outlaw-forge:menu-import", ());
                }
                "menu-save" => {
                    let _ = app_handle.emit("outlaw-forge:menu-save", ());
                }
                "menu-export" => {
                    let _ = app_handle.emit("outlaw-forge:menu-export", ());
                }
                "menu-exit" => {
                    app_handle.exit(0);
                }
                "menu-undo" => {
                    let _ = app_handle.emit("outlaw-forge:menu-undo", ());
                }
                "menu-redo" => {
                    let _ = app_handle.emit("outlaw-forge:menu-redo", ());
                }
                "menu-center-bed" => {
                    let _ = app_handle.emit("outlaw-forge:menu-center-bed", ());
                }
                "menu-wireframe" => {
                    let _ = app_handle.emit("outlaw-forge:menu-wireframe", ());
                }
                "menu-reset-camera" => {
                    let _ = app_handle.emit("outlaw-forge:menu-reset-camera", ());
                }
                "menu-fullscreen" => {
                    if let Some(window) = app_handle.get_webview_window("main") {
                        if let Ok(is_fs) = window.is_fullscreen() {
                            let _ = window.set_fullscreen(!is_fs);
                        }
                    }
                }
                "menu-about" => {
                    let _ = app_handle.emit("outlaw-forge:menu-about", ());
                }
                _ => {}
            }
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<SidecarState>();
                state.shutdown();
            }
        });

    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building outlaw forge desktop application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit = event {
            let state = app_handle.state::<SidecarState>();
            state.shutdown();
        }
    });
}
