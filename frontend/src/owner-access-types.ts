export type OwnerAccessRequest = {
  id: number; user_id: number; email: string; details: string;
  status: "pending" | "approved" | "rejected";
  created_at: string; decided_at: string | null; decision_note: string | null;
};
export type OwnerAccessPageData = { items: OwnerAccessRequest[]; has_next: boolean };
