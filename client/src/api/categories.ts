import { apiGet } from "./client";
import type { CategoryDetail, CategoryList } from "@/types/api";

// List categories — flat, tree built client-side.
export function listCategories(): Promise<CategoryList> {
  return apiGet<CategoryList>("/api/categories");
}

// Category detail — children + parent path.
export function getCategoryDetail(id: string): Promise<CategoryDetail> {
  return apiGet<CategoryDetail>(
    `/api/categories/${encodeURIComponent(id)}`
  );
}