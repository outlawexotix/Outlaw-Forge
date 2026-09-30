/**
 * React 18 / 19 compatibility polyfill for @react-three/fiber and Three.js reconciliation
 */
import * as React from 'react';

if (typeof window !== 'undefined') {
  const ReactAny = React as any;
  if (!ReactAny.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED) {
    ReactAny.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = {
      ReactCurrentOwner: { current: null },
      ReactCurrentDispatcher: { current: null },
      ReactCurrentBatchConfig: { transition: null },
    };
  } else if (!ReactAny.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner) {
    ReactAny.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner = { current: null };
  }
}

export {};
