// Hook — subscribe to bills-source notifications.
// Returns a counter that changes on hydrate/reset → forces useMemo deps in
// existing components to re-compute (they keep calling getMonths/getAllEvents).

import { useEffect, useState } from "react";

import { subscribe } from "@/lib/bills-source";

export function useBillsSourceSubscription(): number {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    return subscribe(() => setVersion((v) => v + 1));
  }, []);
  return version;
}
