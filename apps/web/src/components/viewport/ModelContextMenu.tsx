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
  | 'mirror_x'
  | 'mirror_y'
  | 'mirror_z'
  | 'delete';

interface ModelContextMenuProps {
  x: number;
  y: number;
  onAction: (action: ModelContextAction) => void;
  onClose: () => void;
}

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

export const ModelContextMenu: React.FC<ModelContextMenuProps> = ({ x, y, onAction, onClose }) => {
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
