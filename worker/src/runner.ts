import { Container } from "@cloudflare/containers";

export class Runner extends Container {
  defaultPort = 8080;
  sleepAfter = "5m";
  enableInternet = false;
}
