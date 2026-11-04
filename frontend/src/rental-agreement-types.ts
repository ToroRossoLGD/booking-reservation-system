export type RentalAgreement = {
  id: number; inquiry_id: number; title: string; currency: string; timezone: string;
  start_date: string; end_date: string; months: number; monthly_cents: number; deposit_cents: number;
  notes: string; status: "proposed" | "accepted" | "declined" | "withdrawn"; version: number;
  created_at: string; accepted_at: string | null;
};
export type AgreementInput = { request_id: string; start_date: string; months: number; monthly_cents: number; deposit_cents: number; notes: string };
export type AgreementAction = "accept" | "decline" | "withdraw";
export type RentalCharge = { id: number; sequence: number; due_date: string; amount_cents: number; paid: boolean; version: number; updated_at: string | null };
export type ChargeEvent = { id: number; paid: boolean; version: number; created_at: string };
