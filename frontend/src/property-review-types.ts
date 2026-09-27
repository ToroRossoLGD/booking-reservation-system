export type PropertyReview = { id: number; rating: number; comment: string; created_at: string };
export type PropertyReviewInput = { rating: number; comment: string };
export type PropertyReviewPage = { items: PropertyReview[]; total: number; average_rating: number | null; has_next: boolean };
