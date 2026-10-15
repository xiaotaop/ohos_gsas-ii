/** Creates a new sandbox destination atomically. Caller owns and closes FD. */
export const openExclusive: (uri: string) => number;
