import { apiGet, apiPut } from "./client";
import type { Account, AccountBindingUpdate, AccountList } from "@/types/api";

// List accounts — merged PS catalog + local bindings.
export function listAccounts(): Promise<AccountList> {
  return apiGet<AccountList>("/api/accounts");
}

// Update account binding — full replace.
export function updateBinding(
  id: string,
  binding: AccountBindingUpdate
): Promise<Account> {
  return apiPut<Account>(
    `/api/accounts/${encodeURIComponent(id)}/binding`,
    binding
  );
}