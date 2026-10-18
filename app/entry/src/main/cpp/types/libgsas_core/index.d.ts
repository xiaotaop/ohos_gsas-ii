/** CORE_API v1.0 boundary. JSON in and out follows the frozen contract; rejections throw Error with code and retryable. */
export const setEventCallback: (callback: ((eventJson: string) => void) | null) => void;
export const initializeCore: (configJson: string) => Promise<string>;
export const acquireJob: (jobId: string) => void;
export const releaseJob: (jobId: string) => void;
export const startAcquiredJob: (requestJson: string) => string;
export const cancelJob: (jobId: string) => string;
export const getJobSnapshot: (jobId: string) => string;
export const shutdownCore: () => Promise<void>;
