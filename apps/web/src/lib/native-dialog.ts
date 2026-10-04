/**
 * Native Dialog and File System Bridge for Outlaw Forge.
 *
 * Bridges native file open/save dialogs via @tauri-apps/plugin-dialog
 * when running inside the Tauri 2.0 desktop shell, with seamless fallback
 * to standard HTML5 input and anchor downloads in standard web browsers.
 */

export interface DialogFilter {
  name: string;
  extensions: string[];
}

export interface OpenDialogOptions {
  title?: string;
  defaultPath?: string;
  multiple?: boolean;
  directory?: boolean;
  filters?: DialogFilter[];
}

export interface SaveDialogOptions {
  title?: string;
  defaultPath?: string;
  filters?: DialogFilter[];
}

export interface TauriDialogPlugin {
  open: (options?: OpenDialogOptions) => Promise<string | string[] | null>;
  save: (options?: SaveDialogOptions) => Promise<string | null>;
}

/**
 * Check whether the frontend is currently running inside the Tauri desktop shell.
 */
export function isTauri(): boolean {
  return (
    typeof window !== 'undefined' &&
    ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
  );
}

/**
 * Dynamically resolves the Tauri 2 dialog plugin if available.
 */
async function getTauriDialog(): Promise<TauriDialogPlugin | null> {
  if (!isTauri()) {
    return null;
  }

  const win = window as unknown as {
    __TAURI__?: { dialog?: TauriDialogPlugin };
    __TAURI_INTERNALS__?: {
      invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
    };
  };

  if (win.__TAURI__?.dialog) {
    return win.__TAURI__.dialog;
  }

  try {
    // Dynamic import without bundler resolution errors when package is injected at runtime
    const importer = new Function('specifier', 'return import(specifier)');
    const plugin = (await importer('@tauri-apps/plugin-dialog')) as TauriDialogPlugin;
    if (plugin && typeof plugin.open === 'function') {
      return plugin;
    }
  } catch {
    // Fall back to Tauri IPC invocation
  }

  if (win.__TAURI_INTERNALS__?.invoke) {
    const invoke = win.__TAURI_INTERNALS__.invoke;
    return {
      open: async (options?: OpenDialogOptions) => {
        return (await invoke('plugin:dialog|open', { options })) as string | string[] | null;
      },
      save: async (options?: SaveDialogOptions) => {
        return (await invoke('plugin:dialog|save', { options })) as string | null;
      },
    };
  }

  return null;
}

/**
 * Open native OS file picker in Tauri, or null if running in browser or cancelled.
 */
export async function openNativeFileDialog(
  options?: OpenDialogOptions
): Promise<string | string[] | null> {
  const dialog = await getTauriDialog();
  if (!dialog) {
    return null;
  }
  return await dialog.open(options);
}

/**
 * Open native OS save file dialog in Tauri, or null if running in browser or cancelled.
 */
export async function saveNativeFileDialog(
  options?: SaveDialogOptions
): Promise<string | null> {
  const dialog = await getTauriDialog();
  if (!dialog) {
    return null;
  }
  return await dialog.save(options);
}

/**
 * Standard browser file open fallback using a hidden HTML file input.
 */
export function openBrowserFileDialog(accept?: string): Promise<File | null> {
  return new Promise((resolve) => {
    if (typeof document === 'undefined') {
      resolve(null);
      return;
    }

    const input = document.createElement('input');
    input.type = 'file';
    if (accept) {
      input.accept = accept;
    }
    input.style.display = 'none';
    document.body.appendChild(input);

    let resolved = false;

    input.onchange = () => {
      resolved = true;
      const file = input.files?.[0] || null;
      if (input.parentNode) {
        input.parentNode.removeChild(input);
      }
      resolve(file);
    };

    window.addEventListener(
      'focus',
      () => {
        setTimeout(() => {
          if (!resolved) {
            if (input.parentNode) {
              input.parentNode.removeChild(input);
            }
            resolve(null);
          }
        }, 500);
      },
      { once: true }
    );

    input.click();
  });
}

/**
 * Standard browser download fallback using an anchor element.
 */
export function downloadInBrowser(url: string, filename?: string): void {
  if (typeof document === 'undefined') return;

  const anchor = document.createElement('a');
  anchor.href = url;
  if (filename) {
    anchor.download = filename;
  }
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
}

/**
 * Universal file save helper: attempts native Tauri save dialog,
 * otherwise triggers browser anchor download.
 */
export async function saveFileWithFallback(
  downloadUrl: string,
  defaultFilename: string,
  filters?: DialogFilter[]
): Promise<{ success: boolean; nativePath?: string }> {
  if (isTauri()) {
    const chosenPath = await saveNativeFileDialog({
      defaultPath: defaultFilename,
      filters: filters || [
        { name: '3D Mesh Files', extensions: ['stl', 'obj', '3mf', 'step', 'gcode'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });

    if (chosenPath) {
      downloadInBrowser(downloadUrl, defaultFilename);
      return { success: true, nativePath: chosenPath };
    }
    // User cancelled native dialog
    return { success: false };
  }

  // Browser fallback
  downloadInBrowser(downloadUrl, defaultFilename);
  return { success: true };
}
