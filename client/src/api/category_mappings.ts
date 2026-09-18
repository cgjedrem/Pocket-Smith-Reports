// Category mappings API client — GET list, PUT update.

import { apiGet, apiPut } from "./client";
import type {
  CategoryMapping,
  CategoryMappingList,
  CategoryMappingUpdate,
} from "@/types/category_mappings";

// List all category mappings — merged roles + sections + catalog titles.
export function getCategoryMappings(): Promise<CategoryMappingList> {
  return apiGet<CategoryMappingList>("/api/category-mappings");
}

// Update one category — KPI role + detailed section.
export function updateCategoryMapping(
  categoryId: string,
  update: CategoryMappingUpdate
): Promise<CategoryMapping> {
  return apiPut<CategoryMapping>(
    `/api/category-mappings/${encodeURIComponent(categoryId)}`,
    update
  );
}