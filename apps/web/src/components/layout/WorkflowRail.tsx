"use client";

import React from "react";
import { Check } from "lucide-react";
import { OperationRecord } from "@shared/types/api";

interface WorkflowRailProps {
  hasModel: boolean;
  isWatertight: boolean;
  fitsBuildVolume: boolean;
  operations: OperationRecord[];
}

export function WorkflowRail({ hasModel, isWatertight, fitsBuildVolume, operations }: WorkflowRailProps) {
  const operationTypes = new Set(operations.map((operation) => operation.operation_type));
  const prepared = operationTypes.has("AUTO_ORIENT");
  const exported = operationTypes.has("EXPORT") || operationTypes.has("EXPORT_3MF");
  const steps = [
    { label: "Inspect Model", detail: hasModel ? "Geometry loaded" : "Import a model", complete: hasModel },
    { label: "Repair Issues", detail: isWatertight ? "Mesh is watertight" : "Check open geometry", complete: hasModel && isWatertight },
    { label: "Verify Readiness", detail: fitsBuildVolume ? "Build volume passed" : "Review printer fit", complete: hasModel && isWatertight && fitsBuildVolume },
    { label: "Prepare for Print", detail: prepared ? "Orientation optimized" : "Optimize orientation", complete: prepared },
    { label: "Export", detail: exported ? "Print file generated" : "Save STL or 3MF", complete: exported },
  ];

  const activeIndex = Math.max(0, steps.findIndex((step) => !step.complete));

  return (
    <div className="h-[72px] shrink-0 border-t border-neutral-800 bg-[#0b0d10] px-6 flex items-center">
      <div className="grid grid-cols-5 w-full max-w-[1500px] mx-auto">
        {steps.map((step, index) => {
          const active = index === activeIndex;
          return (
            <div key={step.label} className="relative flex items-center min-w-0">
              {index < steps.length - 1 && (
                <div className={`absolute left-7 right-0 top-[13px] h-px ${step.complete ? "bg-amber-500/60" : "bg-neutral-800"}`} />
              )}
              <div className={`relative z-10 h-7 w-7 shrink-0 rounded-full border flex items-center justify-center text-[10px] font-mono font-bold ${
                step.complete
                  ? "border-amber-500 bg-amber-500 text-neutral-950"
                  : active
                    ? "border-amber-500 bg-neutral-950 text-amber-400"
                    : "border-neutral-700 bg-neutral-950 text-neutral-600"
              }`}>
                {step.complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </div>
              <div className="relative z-10 ml-3 min-w-0 bg-[#0b0d10] pr-4">
                <div className={`truncate text-[11px] font-semibold ${active ? "text-amber-400" : step.complete ? "text-neutral-200" : "text-neutral-500"}`}>
                  {step.label}
                </div>
                <div className="mt-0.5 truncate text-[9px] text-neutral-600">{step.detail}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
