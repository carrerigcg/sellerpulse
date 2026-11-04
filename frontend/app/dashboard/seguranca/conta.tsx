"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { codigoValido } from "@/lib/duas-etapas";
import {
  type ContatoSalvo,
  formataTelefone,
  metadadosDeContato,
  normalizaTelefone,
} from "@/lib/telefone";
import { createClient } from "@/lib/supabase/client";

type Novo = { id: string; qr: string; chave: string };
type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; contato: ContatoSalvo; fator: string | null };

const BOTAO =
  "inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface disabled:opacity-40";
const BOTAO_PRINCIPAL =
  "inline-flex min-h-11 items-center rounded-lg bg-accent px-3 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40";
const CAMPO =
  "mt-1.5 w-full max-w-xs rounded-lg border border-line px-3 py-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20";

/** Leva o foco a um elemento que acabou de aparecer, depois da renderização. */
function focaDepois(ref: React.RefObject<HTMLElement | null>) {
  requestAnimationFrame(() => ref.current?.focus());
}

export function ContatoEDuasEtapas() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });

  const carrega = useCallback(async () => {
    try {
      const supabase = createClient();
      const [usuario, fatores] = await Promise.all([
        supabase.auth.getUser(),
        supabase.auth.mfa.listFactors(),
      ]);
      // Sem resposta, não dá para afirmar "Desativada" nem "sem telefone":
      // salvar a partir daí apagaria o número de verdade.
      if (usuario.error || !usuario.data.user || fatores.error || !fatores.data) {
        setEstado({ tipo: "erro" });
        return;
      }
      const meta = usuario.data.user.user_metadata ?? {};
      setEstado({
        tipo: "pronto",
        contato: {
          telefone: typeof meta.telefone === "string" ? meta.telefone : null,
          aceitoEm: typeof meta.whatsapp_aceito_em === "string" ? meta.whatsapp_aceito_em : null,
        },
        fator: fatores.data.totp.find((f) => f.status === "verified")?.id ?? null,
      });
    } catch {
      setEstado({ tipo: "erro" });
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- busca externa (Supabase Auth) na montagem
    carrega();
  }, [carrega]);

  if (estado.tipo === "carregando") {
    return (
      <p role="status" className="mt-6 text-sm text-muted">
        Carregando…
      </p>
    );
  }
  if (estado.tipo === "erro") {
    return (
      <div role="alert" className="mt-6 rounded-xl border border-line p-5">
        <p className="text-sm">Não foi possível carregar os dados da sua conta agora.</p>
        <button
          type="button"
          onClick={() => {
            setEstado({ tipo: "carregando" });
            carrega();
          }}
          className={`mt-3 ${BOTAO}`}
        >
          Tentar de novo
        </button>
      </div>
    );
  }
  return (
    <>
      <Contato salvo={estado.contato} aoSalvar={carrega} />
      <DuasEtapas fator={estado.fator} aoMudar={carrega} />
    </>
  );
}

function Contato({ salvo, aoSalvar }: { salvo: ContatoSalvo; aoSalvar: () => Promise<void> }) {
  const [telefone, setTelefone] = useState(salvo.telefone ? formataTelefone(salvo.telefone) : "");
  const [querWhatsapp, setQuerWhatsapp] = useState(salvo.aceitoEm !== null);
  const [ocupado, setOcupado] = useState(false);
  const [mensagem, setMensagem] = useState<{ tom: "ok" | "erro"; texto: string } | null>(null);
  const semTelefone = !telefone.trim();
  const invalido = mensagem?.tom === "erro" && mensagem.texto.startsWith("Use DDD");

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setMensagem(null);
    const digitos = semTelefone ? null : normalizaTelefone(telefone);
    if (!semTelefone && !digitos) {
      setMensagem({ tom: "erro", texto: "Use DDD + número, como (11) 98765-4321." });
      return;
    }
    setOcupado(true);
    const { error } = await createClient().auth.updateUser({
      data: metadadosDeContato(digitos, querWhatsapp, salvo, new Date()),
    });
    setOcupado(false);
    if (error) {
      setMensagem({ tom: "erro", texto: "Não foi possível salvar agora. Tente de novo." });
      return;
    }
    setMensagem({ tom: "ok", texto: digitos ? "Telefone salvo." : "Telefone removido." });
    await aoSalvar();
  }

  return (
    <section className="mt-6 rounded-xl border border-line p-5" aria-labelledby="titulo-contato">
      <h2 id="titulo-contato" className="text-sm font-semibold">
        Telefone de contato
      </h2>
      <p className="mt-1 text-sm text-muted">
        Opcional. Usamos só para falar com você sobre a sua conta.
      </p>
      <form onSubmit={salvar} className="mt-3 space-y-3">
        <div>
          <label htmlFor="telefone" className="block text-sm font-medium">
            Celular
          </label>
          <input
            id="telefone"
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            value={telefone}
            aria-invalid={invalido || undefined}
            aria-describedby={invalido ? "telefone-dica telefone-erro" : "telefone-dica"}
            onChange={(e) => {
              setTelefone(e.target.value);
              if (!e.target.value.trim()) setQuerWhatsapp(false);
            }}
            className={CAMPO}
          />
          <p id="telefone-dica" className="mt-1.5 text-xs text-muted">
            DDD + número. Deixe vazio e salve para apagar.
          </p>
        </div>
        <div>
          <label className={`flex items-start gap-2 text-sm ${semTelefone ? "text-muted" : ""}`}>
            <input
              type="checkbox"
              checked={querWhatsapp}
              disabled={semTelefone}
              aria-describedby={semTelefone ? "whatsapp-dica" : undefined}
              onChange={(e) => setQuerWhatsapp(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-accent"
            />
            <span>Aceito receber mensagens do SellerPulse por WhatsApp nesse número.</span>
          </label>
          {semTelefone && (
            <p id="whatsapp-dica" className="ml-6 text-xs text-muted">
              Preencha o celular para escolher.
            </p>
          )}
        </div>
        <button type="submit" disabled={ocupado} className={BOTAO}>
          {ocupado ? "Salvando…" : "Salvar"}
        </button>
        {mensagem && (
          <p
            id={mensagem.tom === "erro" ? "telefone-erro" : undefined}
            role={mensagem.tom === "erro" ? "alert" : "status"}
            className={`text-sm ${mensagem.tom === "erro" ? "text-negative" : "text-positive"}`}
          >
            {mensagem.texto}
          </p>
        )}
      </form>
    </section>
  );
}

function DuasEtapas({ fator, aoMudar }: { fator: string | null; aoMudar: () => Promise<void> }) {
  const router = useRouter();
  const [novo, setNovo] = useState<Novo | null>(null);
  const [desativando, setDesativando] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const titulo = useRef<HTMLHeadingElement>(null);
  const campo = useRef<HTMLInputElement>(null);

  function volta() {
    setNovo(null);
    setDesativando(false);
    setCodigo("");
    setErro(null);
    focaDepois(titulo);
  }

  async function comecar() {
    setErro(null);
    setAviso(null);
    setOcupado(true);
    const supabase = createClient();
    // Um fator criado e não confirmado (a pessoa fechou a tela) é apagado,
    // para não acumular nem bater no nome repetido.
    const { data: fatores } = await supabase.auth.mfa.listFactors();
    for (const f of fatores?.all ?? []) {
      if (f.status !== "verified") await supabase.auth.mfa.unenroll({ factorId: f.id });
    }
    const { data, error } = await supabase.auth.mfa.enroll({
      factorType: "totp",
      friendlyName: "App autenticador",
    });
    setOcupado(false);
    if (error || !data) {
      setErro("Não foi possível começar agora. Tente de novo.");
      return;
    }
    setNovo({ id: data.id, qr: data.totp.qr_code, chave: data.totp.secret });
    focaDepois(campo);
  }

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    const digitos = codigoValido(codigo);
    if (!digitos || !novo) {
      setErro("O código tem 6 números. Confira no app e tente de novo.");
      return;
    }
    setErro(null);
    setOcupado(true);
    const { error } = await createClient().auth.mfa.challengeAndVerify({
      factorId: novo.id,
      code: digitos,
    });
    setOcupado(false);
    if (error) {
      setErro("Código incorreto ou vencido. Use o código que está no app agora.");
      return;
    }
    setNovo(null);
    setCodigo("");
    setAviso("Verificação em duas etapas ativada.");
    await aoMudar();
    focaDepois(titulo);
    router.refresh();
  }

  async function desativar(e: React.FormEvent) {
    e.preventDefault();
    const digitos = codigoValido(codigo);
    if (!digitos || !fator) {
      setErro("O código tem 6 números. Confira no app e tente de novo.");
      return;
    }
    setErro(null);
    setOcupado(true);
    const supabase = createClient();
    // Desativar pede a sessão confirmada com o código agora (`aal2`), regra
    // do próprio Supabase: quem só tem a senha não desliga a proteção.
    const { error: erroDoCodigo } = await supabase.auth.mfa.challengeAndVerify({
      factorId: fator,
      code: digitos,
    });
    const { error } = erroDoCodigo
      ? { error: erroDoCodigo }
      : await supabase.auth.mfa.unenroll({ factorId: fator });
    setOcupado(false);
    if (error) {
      setErro(
        erroDoCodigo
          ? "Código incorreto ou vencido. Use o código que está no app agora."
          : "Não foi possível desativar agora. Tente de novo.",
      );
      return;
    }
    await supabase.auth.refreshSession();
    setDesativando(false);
    setCodigo("");
    setAviso("Verificação em duas etapas desativada.");
    await aoMudar();
    focaDepois(titulo);
    router.refresh();
  }

  const campoDoCodigo = (
    <div>
      <label htmlFor="codigo-do-app" className="block text-sm font-medium">
        Código do app
      </label>
      <input
        ref={campo}
        id="codigo-do-app"
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        value={codigo}
        aria-invalid={erro ? true : undefined}
        aria-describedby={erro ? "duas-etapas-erro" : undefined}
        onChange={(e) => setCodigo(e.target.value)}
        className={CAMPO}
      />
    </div>
  );

  return (
    <section className="mt-6 rounded-xl border border-line p-5" aria-labelledby="titulo-duas-etapas">
      <h2
        id="titulo-duas-etapas"
        ref={titulo}
        tabIndex={-1}
        className="text-sm font-semibold outline-none"
      >
        Verificação em duas etapas
      </h2>
      <p role="status" className="sr-only">
        {aviso}
      </p>

      {fator ? (
        <>
          <p className="mt-1 text-sm">
            <strong className="text-positive">Ativa.</strong> Ao entrar, além da senha,
            pedimos o código do seu app autenticador.
          </p>
          {desativando ? (
            <form onSubmit={desativar} className="mt-3 space-y-3">
              <p className="text-sm text-muted">
                Para desativar, confirme com o código que está no app agora.
              </p>
              {campoDoCodigo}
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={ocupado} className={`${BOTAO} text-negative`}>
                  {ocupado ? "Desativando…" : "Desativar"}
                </button>
                <button type="button" disabled={ocupado} onClick={volta} className={BOTAO}>
                  Manter ativa
                </button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => {
                setAviso(null);
                setDesativando(true);
                focaDepois(campo);
              }}
              className={`mt-3 ${BOTAO} text-negative`}
            >
              Desativar
            </button>
          )}
        </>
      ) : novo ? (
        <form onSubmit={confirmar} className="mt-3 space-y-3">
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            <li>
              Abra um app autenticador no celular (Google Authenticator, Microsoft
              Authenticator ou Authy).
            </li>
            <li>Leia o QR code abaixo com o app, ou digite a chave.</li>
            <li>Digite o código de 6 números que o app mostrar.</li>
          </ol>
          {/* QR em SVG como data URL, gerado pelo Supabase: `next/image` não
              otimiza data URL, e o `<img>` simples é o que funciona. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={novo.qr}
            alt="QR code para o app autenticador"
            width={176}
            height={176}
            className="rounded-lg border border-line bg-white p-2"
          />
          <p className="text-sm">
            Chave:{" "}
            <code className="break-all rounded bg-surface px-1.5 py-0.5 text-xs">{novo.chave}</code>
          </p>
          {campoDoCodigo}
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={ocupado} className={BOTAO_PRINCIPAL}>
              {ocupado ? "Confirmando…" : "Ativar"}
            </button>
            <button type="button" disabled={ocupado} onClick={volta} className={BOTAO}>
              Voltar
            </button>
          </div>
        </form>
      ) : (
        <>
          <p className="mt-1 text-sm text-muted">
            Desativada. Com ela ativa, quem descobrir a sua senha ainda precisa do código do
            seu celular para entrar.
          </p>
          <button
            type="button"
            disabled={ocupado}
            onClick={comecar}
            className={`mt-3 ${BOTAO_PRINCIPAL}`}
          >
            {ocupado ? "Preparando…" : "Ativar"}
          </button>
        </>
      )}

      {erro && (
        <p
          id="duas-etapas-erro"
          role="alert"
          className="mt-3 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative"
        >
          {erro}
        </p>
      )}
    </section>
  );
}
