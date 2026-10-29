import {
  address,
  appendTransactionMessageInstructions,
  createKeyPairSignerFromBytes,
  createNoopSigner,
  createSolanaRpc,
  createTransactionMessage,
  getBase64EncodedWireTransaction,
  getBase64Encoder,
  getSignatureFromTransaction,
  getTransactionDecoder,
  partiallySignTransactionMessageWithSigners,
  pipe,
  setTransactionMessageFeePayerSigner,
  setTransactionMessageLifetimeUsingBlockhash,
  type Address,
  type Base64EncodedWireTransaction,
  type Signature,
} from "@solana/kit";
import {
  TOKEN_PROGRAM_ADDRESS,
  findAssociatedTokenPda,
  getTransferCheckedInstruction,
} from "@solana-program/token";
import type { Env } from "./env";

const DECIMALS = 6;

export type Chain = Awaited<ReturnType<typeof chain>>;
export type Status = "confirmed" | "failed" | "pending";

export async function chain(env: Env) {
  if (!env.HOT_WALLET_KEY || !env.SOLANA_RPC_URL) throw new Error("HOT_WALLET_KEY and SOLANA_RPC_URL secrets are required");
  return {
    rpc: createSolanaRpc(env.SOLANA_RPC_URL),
    hot: await createKeyPairSignerFromBytes(new Uint8Array(JSON.parse(env.HOT_WALLET_KEY))),
    mint: address(env.USDC_MINT),
  };
}

const tokenAccount = async (c: Chain, owner: Address) =>
  (await findAssociatedTokenPda({ owner, mint: c.mint, tokenProgram: TOKEN_PROGRAM_ADDRESS }))[0];

// USDC transfer between existing USDC accounts, the hot wallet paying fees; signed by every key we hold.
export async function transfer(c: Chain, from: Address, to: Address, amount: number) {
  const [source, destination] = await Promise.all([tokenAccount(c, from), tokenAccount(c, to)]);
  const authority = from === c.hot.address ? c.hot : createNoopSigner(from);
  const { value: blockhash } = await c.rpc.getLatestBlockhash({ commitment: "confirmed" }).send();
  const message = pipe(
    createTransactionMessage({ version: 0 }),
    (m) => setTransactionMessageFeePayerSigner(c.hot, m),
    (m) => setTransactionMessageLifetimeUsingBlockhash(blockhash, m),
    (m) =>
      appendTransactionMessageInstructions(
        // Never create the destination's USDC account: its owner could close it and keep the SOL we paid for it.
        [getTransferCheckedInstruction({ source, mint: c.mint, destination, authority, amount: BigInt(amount), decimals: DECIMALS })],
        m,
      ),
  );
  const tx = await partiallySignTransactionMessageWithSigners(message);
  return {
    wire: getBase64EncodedWireTransaction(tx),
    signature: getSignatureFromTransaction(tx),
    lastValid: Number(blockhash.lastValidBlockHeight),
  };
}

export const signatureOf = (wire: string) =>
  getSignatureFromTransaction(getTransactionDecoder().decode(getBase64Encoder().encode(wire)));

export async function send(c: Chain, wire: string) {
  await c.rpc.sendTransaction(wire as Base64EncodedWireTransaction, { encoding: "base64", preflightCommitment: "confirmed" }).send();
}

export async function status(c: Chain, signature: string, lastValid: number): Promise<Status> {
  const { value: [s] } = await c.rpc.getSignatureStatuses([signature as Signature], { searchTransactionHistory: true }).send();
  if (s?.err) return "failed";
  if (s && s.confirmationStatus !== "processed") return "confirmed";
  if (!s && Number(await c.rpc.getBlockHeight({ commitment: "confirmed" }).send()) > lastValid) return "failed";
  return "pending";
}

export const hotBalances = (c: Chain) => balances(c, c.hot.address);

export async function balances(c: Chain, owner: Address) {
  const [{ value: lamports }, usdc] = await Promise.all([
    c.rpc.getBalance(owner).send(),
    tokenAccount(c, owner)
      .then((a) => c.rpc.getTokenAccountBalance(a).send())
      .then((r) => Number(r.value.amount))
      .catch(() => 0),
  ]);
  return { sol: Number(lamports) / 1e9, usdc };
}

export const isAddress = (text: string) => {
  try {
    address(text);
    return true;
  } catch {
    return false;
  }
};
