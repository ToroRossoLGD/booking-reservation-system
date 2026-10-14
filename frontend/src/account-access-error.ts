import { ApiError } from "./api";

export function accountAccessError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return error.message;
    if (error.status === 401) return "Email adresa ili lozinka nisu ispravni.";
    if (error.status === 409) return "Nalog sa ovom email adresom već postoji. Prijavi se ili zatraži novu lozinku.";
    if (error.status === 403) return "Pristup trenutno nije dozvoljen za ovaj nalog ili režim rada.";
    if (error.status === 422) return "Proveri email adresu i lozinku. Lozinka mora imati najmanje 8 znakova.";
    if (error.status >= 500) return "Prijava trenutno nije dostupna. Pokušaj ponovo kasnije.";
  }
  return "Zahtev nije uspeo. Proveri vezu i pokušaj ponovo.";
}
