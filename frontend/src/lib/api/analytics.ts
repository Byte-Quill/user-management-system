import { request } from "./client";

import type { Analytics } from "@/types";

export const fetchAnalytics = () => request<Analytics>("/analytics/");
