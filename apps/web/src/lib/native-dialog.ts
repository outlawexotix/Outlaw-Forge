/**
 * Native Dialog and File System Bridge for Outlaw Forge.
 *
 * Bridges native file open/save dialogs via @tauri-apps/plugin-dialog
 * and @tauri-apps/plugin-fs when running inside the Tauri desktop shell,
 * with clean fallback to standard HTML5 input and anchor downloads in
 * standard web browsers.
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

export interface TauriFsPlugin {
  writeFile: (path: string, data: Uint8Array) => Promise<void>;
  writeBinaryFile?: (path: string, data: Uint8Array) => Promise<void>;
  readFile?: (path: string) => Promise<Uint8Array>;
  readBinaryFile?: (path: string) => Promise<Uint8Array>;
}

export interface SaveFileResult {
  success: boolean;
  method?: 'native_fs' | 'browser_download';
  nativePath?: string;
  cancelled?: boolean;
  error?: string;
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
 * Dynamically resolves the Tauri filesystem plugin or IPC invocation if available.
 */
async function getTauriFs(): Promise<TauriFsPlugin | null> {
  if (!isTauri()) {
    return null;
  }

  const win = window as unknown as {
    __TAURI__?: {
      fs?: {
        writeFile?: (path: string, data: Uint8Array) => Promise<void>;
        writeBinaryFile?: (path: string, data: Uint8Array) => Promise<void>;
        readFile?: (path: string) => Promise<Uint8Array>;
        readBinaryFile?: (path: string) => Promise<Uint8Array>;
      };
    };
    __TAURI_INTERNALS__?: {
      invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
    };
  };

  if (win.__TAURI__?.fs && (win.__TAURI__.fs.writeFile || win.__TAURI__.fs.writeBinaryFile)) {
    const fs = win.__TAURI__.fs;
    return {
      writeFile: async (path: string, data: Uint8Array) => {
        if (fs.writeFile) {
          await fs.writeFile(path, data);
        } else if (fs.writeBinaryFile) {
          await fs.writeBinaryFile(path, data);
        }
      },
      readFile: async (path: string) => {
        if (fs.readFile) {
          return await fs.readFile(path);
        } else if (fs.readBinaryFile) {
          return await fs.readBinaryFile(path);
        }
        throw new Error('Read file method not available on Tauri fs');
      },
    };
  }

  try {
    // Dynamic import to prevent bundler resolution errors when package is injected at runtime
    const importer = new Function('specifier', 'return import(specifier)');
    const plugin = (await importer('@tauri-apps/plugin-fs')) as TauriFsPlugin;
    if (plugin && typeof plugin.writeFile === 'function') {
      return plugin;
    }
  } catch {
    // Fall back to Tauri IPC invocation
  }

  if (win.__TAURI_INTERNALS__?.invoke) {
    const invoke = win.__TAURI_INTERNALS__.invoke;
    return {
      writeFile: async (path: string, data: Uint8Array) => {
        try {
          await invoke('plugin:fs|write_file', { path, contents: Array.from(data) });
        } catch {
          await invoke('plugin:fs|writeFile', { path, data: Array.from(data) });
        }
      },
      readFile: async (path: string) => {
        try {
          const res = (await invoke('plugin:fs|read_file', { path })) as number[] | Uint8Array;
          return res instanceof Uint8Array ? res : new Uint8Array(res);
        } catch {
          const res = (await invoke('plugin:fs|readFile', { path })) as number[] | Uint8Array;
          return res instanceof Uint8Array ? res : new Uint8Array(res);
        }
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
 * Write binary data directly to a local filesystem path in the Tauri shell.
 */
export async function writeNativeFile(path: string, data: Uint8Array): Promise<boolean> {
  const fs = await getTauriFs();
  if (!fs) {
    return false;
  }
  try {
    await fs.writeFile(path, data);
    return true;
  } catch {
    return false;
  }
}

/**
 * Ingestion bridge: Reads a local filesystem path in Tauri desktop shell
 * and converts it to a standard HTML5 File object for apiClient.importModel.
 */
export async function readNativeFileAsFile(filePath: string): Promise<File | null> {
  const fs = await getTauriFs();
  if (!fs || !fs.readFile) {
    return null;
  }
  try {
    const bytes = await fs.readFile(filePath);
    const fileName = filePath.split(/[/\\]/).pop() || 'model.stl';
    const blob = new Blob([bytes as unknown as BlobPart]);
    return new File([blob], fileName);
  } catch {
    return null;
  }
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
 * Universal file save helper:
 * - In pure web: cleanly downloads via browser anchor download and returns { success: true, method: 'browser_download' }.
 * - In Tauri: prompts for destination with native OS save dialog. If cancelled, returns { success: false, cancelled: true }.
 *   If a path is selected, writes bytes using Tauri filesystem or IPC if available, or reports status accurately.
 *   Never silently redirects to browser Downloads folder when a native path was chosen.
 */
export async function saveFileWithFallback(
  downloadUrl: string,
  defaultFilename: string,
  filters?: DialogFilter[]
): Promise<SaveFileResult> {
  if (isTauri()) {
    const chosenPath = await saveNativeFileDialog({
      defaultPath: defaultFilename,
      filters: filters || [
        { name: '3D Mesh Files', extensions: ['stl', 'obj', '3mf', 'step', 'gcode'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });

    if (!chosenPath) {
      // User cancelled native dialog
      return { success: false, cancelled: true };
    }

    // Attempt native file write via Tauri filesystem plugin or IPC
    const fs = await getTauriFs();
    if (fs) {
      try {
        if (typeof fetch === 'function') {
          const res = await fetch(downloadUrl);
          if (!res.ok) {
            return {
              success: false,
              nativePath: chosenPath,
              error: `Failed to download source file: ${res.status} ${res.statusText}`,
            };
          }
          const buffer = await res.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          await fs.writeFile(chosenPath, bytes);
          return { success: true, method: 'native_fs', nativePath: chosenPath };
        }
      } catch (err) {
        return {
          success: false,
          nativePath: chosenPath,
          error: err instanceof Error ? err.message : String(err),
        };
      }
    }

    // In desktop shell without native fs plugin, report native selection accurately
    // without silently downloading into the browser Downloads folder.
    return { success: true, nativePath: chosenPath };
  }

  // Pure Web Browser environment: cleanly download via browser anchor download
  downloadInBrowser(downloadUrl, defaultFilename);
  return { success: true, method: 'browser_download' };
}
