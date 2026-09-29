# Outlaw Forge - AI Architecture & Provider Contracts

## 1. Architectural Directive

In Outlaw Forge, **AI recommendations are strictly advisory and completely decoupled from deterministic geometry calculations**.

1. **Geometric Invariance**: All spatial dimensions, unit conversions, volume calculations, bounding boxes, and printer fit checks are performed by pure mathematical algorithms (`trimesh`, `numpy`, linear algebra) with zero AI inference.
2. **Advisory Role**: AI capabilities provide contextual suggestions, natural language analysis, orientation ideas, or project planning. They never silently modify geometry, units, or project models.
3. **Provider Agnostic**: AI providers (Anthropic, OpenAI, Google Gemini, Local Ollama) implement standardized provider interfaces.

---

## 2. Deferred AI Provider Interfaces (Milestone 1 Specification)

```typescript
// Shared Interface Contracts for Future AI Modules

export interface AIReferenceAnalysisRequest {
  projectId: string;
  imageUrls: string[];
  projectType: string;
  userPrompt?: string;
}

export interface AIReferenceAnalysisResponse {
  characterTraits: string[];
  suggestedDimensions: {
    recommendedHeightMm: number;
    proportionalWidthMm: number;
    proportionalDepthMm: number;
  };
  complexityScore: number; // 1-10
  featureHighlights: string[];
}

export interface AIOrientationSuggestionRequest {
  modelId: string;
  printerId: string;
  triangleCount: number;
  boundingDimensions: [number, number, number];
}

export interface AIOrientationSuggestionResponse {
  recommendedRotations: Array<{
    rotationDegrees: [number, number, number];
    rationale: string;
    estimatedSupportVolumeReductionPercent: number;
    criticalSurfacePreservation: string;
  }>;
}

export interface AIPrintDoctorDiagnosisRequest {
  projectId: string;
  printerModel: string;
  symptomDescription: string;
  failurePhotos?: string[];
  currentSettings: {
    layerHeightMm: number;
    infillPercent: number;
    printTempC: number;
    bedTempC: number;
    speedMmS: number;
  };
}

export interface AIPrintDoctorDiagnosisResponse {
  probableCauses: Array<{
    cause: string;
    confidence: number;
    remediationSteps: string[];
  }>;
  recommendedSettingAdjustments: Record<string, any>;
}
```

---

## 3. Boundary Guarantees

- **No Implicit Execution**: AI outputs are returned to the user as suggestions. A human user must explicitly review and confirm before any transformation or parameter change is applied.
- **Auditable Provenance**: If an AI suggestion leads to a transformation (e.g., applying a suggested scale), the operation log explicitly records `source: "ai_suggestion"` with prompt and parameter metadata.
