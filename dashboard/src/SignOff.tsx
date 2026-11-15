import { useState } from "react";
import { paths, postJson, type Handler } from "./api";
import { formatTime, money } from "./format";
import { Problem } from "./ui";
import { useApi } from "./useApi";

export function SignedOff({
  handlerId,
  at,
}: Readonly<{ handlerId: string; at: string }>) {
  const { data: handlers } = useApi<Handler[]>(paths.handlers);
  const name =
    handlers?.find((h) => h.handler_id === handlerId)?.name ?? handlerId;
  return (
    <>
      Signed off by {name} on {formatTime(at)}
    </>
  );
}

export function SignOff({
  claimId,
  payout,
  onSignedOff,
}: Readonly<{ claimId: string; payout: number; onSignedOff: () => void }>) {
  const { data: handlers } = useApi<Handler[]>(paths.handlers);
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const eligible = handlers?.filter((h) => h.can_approve_over_limit) ?? [];
  const handlerId = picked === "" ? (eligible[0]?.handler_id ?? "") : picked;

  async function signOff() {
    setBusy(true);
    try {
      await postJson(paths.signOff(claimId), { handler_id: handlerId });
      setError(undefined);
      onSignedOff();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="sign-off"
      onSubmit={(event) => {
        event.preventDefault();
        void signOff();
      }}
    >
      <p className="sign-off-note">
        Payment of {money(payout)} waits for a handler&apos;s sign-off.
      </p>
      <div className="sign-off-controls">
        <label>
          Handler{" "}
          <select
            value={handlerId}
            onChange={(event) => {
              setPicked(event.target.value);
            }}
          >
            {eligible.map((h) => (
              <option key={h.handler_id} value={h.handler_id}>
                {h.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy || handlerId === ""}>
          Sign off
        </button>
      </div>
      {error && <Problem message={error} />}
    </form>
  );
}
