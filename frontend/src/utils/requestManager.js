/**
 * RequestLifecycleManager
 * Centralized manager for handling authenticated request lifecycles,
 * preventing race conditions, stale response injection, and uncoordinated aborts.
 */

export class RequestLifecycleManager {
  constructor() {
    this.authGeneration = 0;
    this.currentUserId = null;
    this.controllers = new Map(); // category -> AbortController
  }

  /**
   * Advances the auth generation, aborts all in-flight requests,
   * and sets the active user identity.
   */
  nextAuthGeneration(userId = null) {
    this.authGeneration += 1;
    this.currentUserId = userId;
    this.abortAll();
    return this.authGeneration;
  }

  /**
   * Sets the current user ID without advancing generation (e.g. on restore)
   */
  setCurrentUser(userId) {
    this.currentUserId = userId;
  }

  /**
   * Aborts requests for a specific category without affecting others.
   */
  abortCategory(category) {
    const ctrl = this.controllers.get(category);
    if (ctrl) {
      try {
        ctrl.abort();
      } catch {
        /* ignore */
      }
      this.controllers.delete(category);
    }
  }

  /**
   * Aborts all active in-flight requests across all categories.
   */
  abortAll() {
    for (const ctrl of this.controllers.values()) {
      try {
        ctrl.abort();
      } catch {
        /* ignore */
      }
    }
    this.controllers.clear();
  }

  /**
   * Creates a guarded request for a specific category.
   * Automatically aborts any existing request of the same category.
   *
   * @param {string} category - e.g. 'chat', 'image', 'sessions', 'history', 'auth'
   * @param {Object} options - { userId, sessionId }
   * @returns {Object} { signal, isValid(currentSessionId), complete(), abort(), generation }
   */
  createRequest(category, { userId, sessionId } = {}) {
    // Abort previous request of the same category
    this.abortCategory(category);

    const controller = new AbortController();
    this.controllers.set(category, controller);

    const capturedGen = this.authGeneration;
    const capturedUser = userId !== undefined ? userId : this.currentUserId;
    const capturedSession = sessionId !== undefined ? sessionId : null;

    const isValid = (currentSessionId = null) => {
      // 1. Controller must not be aborted
      if (controller.signal.aborted) return false;

      // 2. Auth generation must match
      if (this.authGeneration !== capturedGen) return false;

      // 3. User identity must match (if user was specified)
      if (capturedUser !== undefined && capturedUser !== null) {
        if (this.currentUserId !== capturedUser) return false;
      }

      // 4. Session ID must match for consultation-scoped requests
      if (capturedSession !== undefined && capturedSession !== null) {
        if (currentSessionId !== null && currentSessionId !== undefined) {
          if (currentSessionId !== capturedSession) return false;
        }
      }

      return true;
    };

    const complete = () => {
      if (this.controllers.get(category) === controller) {
        this.controllers.delete(category);
      }
    };

    return {
      signal: controller.signal,
      isValid,
      complete,
      abort: () => {
        try {
          controller.abort();
        } catch {
          /* ignore */
        }
        complete();
      },
      generation: capturedGen,
      category,
    };
  }
}

// Default singleton instance
export const requestManager = new RequestLifecycleManager();
