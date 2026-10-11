"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getApi } from "./client";
import type { Brief, ReviewAction } from "./types";

export const usePatients = () => useQuery({ queryKey: ["patients"], queryFn: () => getApi().listPatients() });
export const useBrief = (id: string) =>
  useQuery({ queryKey: ["brief", id], queryFn: () => getApi().getBrief(id), enabled: !!id });
export const useSource = (id: string, chunkId: string) =>
  useQuery({ queryKey: ["source", id, chunkId], queryFn: () => getApi().getSource(id, chunkId), enabled: !!id && !!chunkId });
export const useSuggestions = (id: string) =>
  useQuery({ queryKey: ["suggestions", id], queryFn: () => getApi().suggestedQuestions(id), enabled: !!id });
export const useAudit = () => useQuery({ queryKey: ["audit"], queryFn: () => getApi().audit() });

export function useReview(patientId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ insightId, action }: { insightId: string; action: ReviewAction }) =>
      getApi().review(insightId, action),
    onMutate: async ({ insightId, action }) => {
      await qc.cancelQueries({ queryKey: ["brief", patientId] });
      const prev = qc.getQueryData<Brief>(["brief", patientId]);
      if (prev) {
        qc.setQueryData<Brief>(["brief", patientId], {
          ...prev,
          snapshot: prev.snapshot.map((i) =>
            i.id !== insightId
              ? i
              : action === "reviewed"
                ? { ...i, review_state: "reviewed" }
                : { ...i, feedback: action },
          ),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(["brief", patientId], ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
    },
  });
}

export const useChat = (patientId: string) =>
  useMutation({ mutationFn: (question: string) => getApi().chat(patientId, question) });

export const useUpload = () =>
  useMutation({ mutationFn: ({ id, file }: { id: string; file: File }) => getApi().upload(id, file) });
