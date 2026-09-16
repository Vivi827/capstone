import { httpPallyApi } from "@/lib/api/http-client";
import type { PallyApi } from "@/lib/api/contracts";

export const pallyApi: PallyApi = httpPallyApi;

export { PallyApiError } from "@/lib/api/contracts";
export type * from "@/lib/api/contracts";
