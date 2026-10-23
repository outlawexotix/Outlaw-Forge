'use client';

import React, { useEffect, useRef } from 'react';

export type ModelContextAction =
  | 'move'
  | 'rotate'
  | 'scale'
  | 'slice'
  | 'inspect'
  | 'lay_flat'
  | 'duplicate'
  | 'toggle_visibility'
  | 'mirror_x'
  | 'mirror_y'
  | 'mirror_z'
  | 'delete';

interface ModelContextMenuProps {
  x: number;
  y: number;
  onAction: (action: ModelContextAction) => void;
  color?: string;
  onColorChange?: (color: string | null) => void;
  onClose: () => void;
  hidden?: boolean;
}

const MODEL_COLORS = ['#38bdf8', '#22c55e', '#f97316', '#e879f9', '#f59e0b', '#f8fafc'];

const ActionButton: React.FC<{
  label: string;
  action: ModelContextAction;
  onAction: (action: ModelContextAction) => void;
  danger?: boolean;
}> = ({ label, action, onAction, danger }) => (
  <button
    type="button"
    className={`w-full px-3 py-1.5 text-left text-[11px] font-mono rounded transition ${
      danger ? 'text-rose-300 hover:bg-rose-950/70' : 'text-slate-200 hover:bg-cyan-900/70'
    }`}
    onClick={() => onAction(action)}
  >
    {label}
  </button>
);

export const ModelContextMenu: React.FC<ModelContextMenuProps> = ({
  x, y, onAction, onColorChange, color, onClose, hidden = false,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) onClose();
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="absolute z-50 min-w-[190px] rounded-lg border border-cyan-700/70 bg-slate-950/95 p-1.5 shadow-2xl backdrop-blur-md"
      style={{ left: x, top: y }}
      onContextMenu={(event) => event.preventDefault()}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <div className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-widest text-cyan-300">Geometry</div>
      <ActionButton label="Move" action="move" onAction={onAction} />
      <ActionButton label="Rotate" action="rotate" onAction={onAction} />
      <ActionButton label="Scale" action="scale" onAction={onAction} />
      <ActionButton label="Lay flat / orient" action="lay_flat" onAction={onAction} />
      <ActionButton label="Slice model" action="slice" onAction={onAction} />
      <div className="my-1 border-t border-slate-800" />
      <div className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-widest text-cyan-300">Mesh & object</div>
      <ActionButton label="Inspect overhangs" action="inspect" onAction={onAction} />
      <ActionButton label="Copy / duplicate" action="duplicate" onAction={onAction} />
      <ActionButton label={hidden ? 'Show model' : 'Hide model'} action="toggle_visibility" onAction={onAction} />
      {onColorChange && (
        <div className="px-3 pb-1 pt-2">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-cyan-300">Object color</div>
          <div className="flex items-center gap-1.5">
            {MODEL_COLORS.map((swatch) => (
              <button
                key={swatch}
                type="button"
                aria-label={`Set object color ${swatch}`}
                aria-pressed={color === swatch}
                title={swatch}
                onClick={() => onColorChange(swatch)}
                className={`h-5 w-5 rounded-full border ${color === swatch ? 'border-white ring-1 ring-cyan-400' : 'border-slate-600 hover:border-white'}`}
                style={{ backgroundColor: swatch }}
              />
            ))}
            <button
              type="button"
              aria-label="Reset object color"
              title="Reset color"
              onClick={() => onColorChange(null)}
              className="h-5 rounded border border-slate-600 px-1.5 text-[9px] text-slate-300 hover:border-cyan-400"
            >
              Auto
            </button>
          </div>
        </div>
      )}
      <div className="px-3 pb-0.5 pt-1 text-[10px] text-slate-500">Mirror</div>
      <div className="grid grid-cols-3 gap-1 px-1">
        <ActionButton label="X" action="mirror_x" onAction={onAction} />
        <ActionButton label="Y" action="mirror_y" onAction={onAction} />
        <ActionButton label="Z" action="mirror_z" onAction={onAction} />
      </div>
      <div className="my-1 border-t border-slate-800" />
      <ActionButton label="Delete model" action="delete" onAction={onAction} danger />
    </div>
  );
};
