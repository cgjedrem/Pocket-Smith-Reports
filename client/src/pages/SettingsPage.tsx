import { AccountTable } from "@/components/AccountTable";
import { ApiKeySection } from "@/components/ApiKeySection";
import { CategoryMappingsEditor } from "@/components/settings/CategoryMappingsEditor";
import { PartnerList } from "@/components/PartnerList";

// Settings — 4 independent sections.
export function SettingsPage() {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h1 className="mb-4">Settings</h1>

      <section className="mt-4 border-t border-border pt-4 first:mt-0 first:border-t-0 first:pt-0">
        <h2 className="mb-3 text-lg">PocketSmith API Key</h2>
        <ApiKeySection />
      </section>

      <section className="mt-4 border-t border-border pt-4">
        <h2 className="mb-3 text-lg">Partners</h2>
        <PartnerList />
      </section>

      <section className="mt-4 border-t border-border pt-4">
        <h2 className="mb-3 text-lg">Accounts</h2>
        <AccountTable />
      </section>

      <section className="mt-4 border-t border-border pt-4">
        <h2 className="mb-3 text-lg">Category Mappings</h2>
        <CategoryMappingsEditor />
      </section>
    </div>
  );
}