export type RentalAction = "reply" | "propose" | "confirm" | "decline" | "close" | "withdraw";
export interface RentalInquiryInput {
  request_id: string;
  move_in: string;
  duration_months: number;
  message: string;
}
export interface RentalUpdate {
  version: number;
  action: RentalAction;
  owner_reply?: string;
  viewing_at?: string;
}
export interface RentalInquiry {
  id: number;
  property_id: number;
  title: string;
  monthly_price_cents: number;
  currency: string;
  move_in: string;
  duration_months: number;
  message: string;
  owner_reply: string;
  viewing_at: string | null;
  status: "open" | "viewing_proposed" | "viewing_confirmed" | "closed" | "withdrawn";
  version: number;
  created_at: string;
}
export interface RentalInquiryPage {
  items: RentalInquiry[];
  total: number;
  has_next: boolean;
}
export const rentalStatus: Record<RentalInquiry["status"], string> = {
  open: "Otvoren upit",
  viewing_proposed: "Predložen termin",
  viewing_confirmed: "Razgledanje potvrđeno",
  closed: "Zatvoren upit",
  withdrawn: "Povučen upit",
};
