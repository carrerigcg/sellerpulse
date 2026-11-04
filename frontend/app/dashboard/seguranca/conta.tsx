"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { codigoValido } from "@/lib/duas-etapas";
import { createClient } from "@/lib/supabase/client";
import { formataTelefone, metadadosDeContato, normalizaTelefone } from "@/lib/telefone";

type Novo = { id: string; qr: string; chave: string };

const BOTAO =
  "inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface disabled:opacity-40";
const BOTAO_PRINCIPAL =
  "inline-flex min-h-11 items-center rounded-lg bg-accent px-3 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40";
const CAMPO =
  "mt-1.5 w-full max-w-xs rounded-lg border border-line px-3 py-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20";

export function ContatoEDuasEtapas() {
  const [carregado, setCarregado] = useState(false);
  const [telefone, setTelefone] = useState("");
  const [aceite, setAceite] = useState<string | null>(null);
  const [fator, setFator] = useState<string | null>(null);

  const carrega = useCallback(async () => {
    const supabase = createClient();
    const [{ data: usuario }, { data: fatores }] = await Promise.all([
      supabase.auth.getUser(),
      supabase.auth.mfa.listFactors(),
    ]);
    const meta = usuario.user?.user_metadata ?? {};
    setTelefone(typeof meta.telefone === "string" ? formataTelefone(meta.telefone) : "");
    setAceite(typeof meta.whatsapp_aceito_em === "string" ? meta.whatsapp_aceito_em : null);
    setFator(fatores?.totp.find((f) => f.status === "verified")?.id ?? null);
    setCarregado(true);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- busca externa (Supabase Auth) na montagem
    carrega();
  }, [carrega]);

  if (!carregado) return <p className="mt-6 text-sm text-muted">Carregando…</p>;

  return (
    <>
      <Contato telefoneInicial={telefone} aceiteInicial={aceite} aoSalvar={carrega} />
      <DuasEtapas fator={fator} aoMudar={carrega} />
    </>
  );
}

function Contato({
  telefoneInicial,
  aceiteInicial,
  aoSalvar,
}: {
  telefoneInicial: string;
  aceiteInicial: string | null;
  aoSalvar: () => Promise<void>;
}) {
  const [telefone, setTelefone] = useState(telefoneInicial);
  const [querWhatsapp, setQuerWhatsapp] = useState(aceiteInicial !== null);
  const [ocupado, setOcupado] = useState(false);
  const [mensagem, setMensagem] = useState<{ tom: "ok" | "erro"; texto: string } | null>(null);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setMensagem(null);
    const digitos = telefone.trim() ? normalizaTelefone(telefone) : null;
    if (telefone.trim() && !digitos) {
      setMensagem({ tom: "erro", texto: "Use DDD + número, como (11) 98765-4321." });
      return;
    }
    setOcupado(true);
    const { error } = await createClient().auth.updateUser({
      data: metadadosDeContato(digitos, querWhatsapp, aceiteInicial, new Date()),
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
    <section className="mt-6 rounded-xl border border-line p-5">
      <h2 className="text-sm font-semibold">Telefone de contato</h2>
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
            onChange={(e) => {
              setTelefone(e.target.value);
              if (!e.target.value.trim()) setQuerWhatsapp(false);
            }}
            className={CAMPO}
          />
        </div>
        <label className={`flex items-start gap-2 text-sm ${telefone.trim() ? "" : "text-muted"}`}>
          <input
            type="checkbox"
            checked={querWhatsapp}
            disabled={!telefone.trim()}
            onChange={(e) => setQuerWhatsapp(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-accent"
          />
          <span>Aceito receber mensagens do SellerPulse por WhatsApp nesse número.</span>
        </label>
        <button type="submit" disabled={ocupado} className={BOTAO}>
          {ocupado ? "Salvando…" : "Salvar"}
        </button>
        {mensagem && (
          <p
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

  async function comecar() {
    setErro(null);
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
    await aoMudar();
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
    await aoMudar();
    router.refresh();
  }

  const campoDoCodigo = (
    <div>
      <label htmlFor="codigo-do-app" className="block text-sm font-medium">
        Código do app
      </label>
      <input
        id="codigo-do-app"
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        value={codigo}
        onChange={(e) => setCodigo(e.target.value)}
        className={CAMPO}
      />
    </div>
  );

  return (
    <section className="mt-6 rounded-xl border border-line p-5">
      <h2 className="text-sm font-semibold">Verificação em duas etapas</h2>

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
                <button type="submit" disabled={ocupado} className={BOTAO}>
                  {ocupado ? "Desativando…" : "Desativar"}
                </button>
                <button
                  type="button"
                  disabled={ocupado}
                  onClick={() => {
                    setDesativando(false);
                    setErro(null);
                  }}
                  className={BOTAO}
                >
                  Manter ativa
                </button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setDesativando(true)}
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
            <button
              type="button"
              disabled={ocupado}
              onClick={() => {
                setNovo(null);
                setCodigo("");
                setErro(null);
              }}
              className={BOTAO}
            >
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
          <button type="button" disabled={ocupado} onClick={comecar} className={`mt-3 ${BOTAO_PRINCIPAL}`}>
            {ocupado ? "Preparando…" : "Ativar"}
          </button>
        </>
      )}

      {erro && (
        <p role="alert" className="mt-3 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}
        </p>
      )}
    </section>
  );
}
