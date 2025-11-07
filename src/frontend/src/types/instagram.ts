export type InstagramIngestRequest = {
  usernames: string[];
  startDate: string;
  endDate: string;
  includeTags?: string[];
  excludeTags?: string[];
  minLikes?: number;
  minComments?: number;
  maxPostsPerUsername?: number;
  includeAbout?: boolean;
  dryRun?: boolean;
};

export type UsernameStats = {
  fetched: number;
  kept: number;
  skipped: {
    date: number;
    inc_tag: number;
    exc_tag: number;
    likes: number;
    comments: number;
    private: number;
    other: number;
  };
};

export type InstagramIngestResponse = {
  actor: {
    runId: string;
    startedAt?: string;
    finishedAt?: string;
    status: string;
  };
  perUsername: Record<string, UsernameStats>;
  itemsKept: number;
};
