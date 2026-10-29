// Creates a hot wallet: keypair file to argv[2] (mode 600, your backup), secret on stdout
// for `wrangler secret put HOT_WALLET_KEY`, address on stderr.
import { generateKeyPairSigner, getAddressEncoder } from "@solana/kit";
import { existsSync, writeFileSync } from "node:fs";

const [, , backup] = process.argv;
if (!backup || existsSync(backup)) throw new Error(`usage: hot-wallet.mjs <new backup file>`);
const signer = await generateKeyPairSigner(true);
const seed = new Uint8Array(await crypto.subtle.exportKey("pkcs8", signer.keyPair.privateKey)).slice(-32);
const secret = JSON.stringify([...seed, ...getAddressEncoder().encode(signer.address)]);
writeFileSync(backup, secret, { mode: 0o600 });
process.stdout.write(secret);
console.error(`hot wallet ${signer.address}`);
