import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/layouts/AppLayout";
import { BillsPage } from "@/pages/BillsPage";
import { BillsPreviewPage } from "@/pages/BillsPreviewPage";
import { MegaReportsPage } from "@/pages/MegaReportsPage";
import { MonthlyReportsPage } from "@/pages/MonthlyReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SyncPage } from "@/pages/SyncPage";

// Router — / redirects to /sync.
export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/sync" replace /> },
      { path: "sync", element: <SyncPage /> },
      { path: "reports", element: <MonthlyReportsPage /> },
      { path: "mega-reports", element: <MegaReportsPage /> },
      { path: "bills", element: <BillsPage /> },
      { path: "bills-preview", element: <BillsPreviewPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);