"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { estaRodando } from "./api";

/**
 * Acompanha um estágio longo (E3..E6) que roda em background no servidor.
 *
 * O POST responde 202 na hora; este hook faz polling do GET enquanto o status
 * for "rodando" e para quando conclui ou falha. O botão do estágio deriva de
 * `rodando`, que vem do servidor — por isso continua correto após um 504, um
 * reload da página ou a UI aberta em outro dispositivo, casos em que o estado
 * local do fetch se perderia.
 *
 * `dispatch` inicia; `poll` lê o estado atual. Ambos falam a mesma forma
 * ({ status, erro? }), então servem os quatro estágios sem variação.
 */
export function useEstagio<T extends { status: string; erro?: string | null }>(
  poll: () => Promise<T>,
  dispatch: () => Promise<T>,
  onError: (m: string) => void,
  intervaloMs = 4000,
) {
  const [state, setState] = useState<T | null>(null);
  const rodando = estaRodando(state);

  // Refs para não recriar o efeito de polling a cada render do pai: as funções
  // (poll/dispatch/onError) costumam ser recriadas inline nos painéis.
  const pollRef = useRef(poll);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    pollRef.current = poll;
    onErrorRef.current = onError;
  });

  // Uma leitura inicial e depois um tick enquanto estiver rodando. Reabrir a
  // página no meio de uma execução cai aqui e retoma o acompanhamento.
  useEffect(() => {
    let vivo = true;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const s = await pollRef.current();
        if (!vivo) return;
        setState(s);
        if (estaRodando(s)) timer = setTimeout(tick, intervaloMs);
      } catch {
        // GET pode falhar transitoriamente (túnel instável): tenta de novo.
        if (vivo) timer = setTimeout(tick, intervaloMs);
      }
    }
    tick();

    return () => {
      vivo = false;
      clearTimeout(timer);
    };
  }, [intervaloMs]);

  const disparar = useCallback(async () => {
    try {
      const s = await dispatch();
      setState(s);
    } catch (e) {
      // 409 (já em andamento) também cai aqui: relê para sincronizar.
      onErrorRef.current(e instanceof Error ? e.message : String(e));
      try {
        setState(await pollRef.current());
      } catch {
        /* mantém o estado anterior */
      }
    }
    // dispatch é estável por vir de lib/api; poll via ref. eslint-disable-next-line
  }, [dispatch]);

  return { state, setState, rodando, erro: state?.erro ?? null, disparar };
}
