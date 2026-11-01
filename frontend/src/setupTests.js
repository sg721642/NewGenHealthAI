import '@testing-library/jest-dom';
import { vi, beforeAll } from 'vitest';

// Polyfill localStorage for happy-dom environments that don't expose it by default
beforeAll(() => {
  if (typeof localStorage === 'undefined' || localStorage === null) {
    const store = {};
    const localStorageMock = {
      getItem: (key) => store[key] ?? null,
      setItem: (key, value) => { store[key] = String(value); },
      removeItem: (key) => { delete store[key]; },
      clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
      get length() { return Object.keys(store).length; },
      key: (i) => Object.keys(store)[i] ?? null,
    };
    Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true });
    Object.defineProperty(window, 'localStorage', { value: localStorageMock, writable: true });
  }
});

// DOM method stubs required by App.jsx animations
global.Element.prototype.scrollIntoView = vi.fn();
global.Element.prototype.scrollTo = vi.fn();
global.window.scroll = vi.fn();
global.window.scrollTo = vi.fn();

if (typeof URL.createObjectURL === 'undefined') {
  URL.createObjectURL = vi.fn(() => 'blob:mock-image');
  URL.revokeObjectURL = vi.fn();
}
