pokerbots.dev

start
  pb login                   sign in with GitHub
  pb init mybot              create mybot/bot.py
  pb test [dir]              play 100 local games against house bots
  pb upload [dir]            upload a new version: v1, v2, ...
  pb deploy v1 --paper       play free games with v1
  pb deploy v1 --live        play for money with v1
  pb stop --paper|--live     stop playing
  pb status                  versions, rating, balance, recent games
  pb watch                   the same, refreshed every 5 seconds
  pb docs [--plain]          show this

money
  pb wallet                  your Solana wallet address and balance
  pb deposit 5               move $5 USDC from your wallet to your balance
  pb withdraw 5              move $5 back to your wallet

  Your wallet key is ~/.config/pokerbots/wallet.json and never leaves your
  machine. Send USDC on Solana to its address, then deposit. We pay the
  network fees. Large withdrawals may wait for review.

bot.py
  class Bot:
      def act(self, state):
          if "check" in state["legal"]:
              return ("check",)
          return ("fold",)

  A new Bot is created for every game. act is called for every decision.
  A late reply (over 20 ms), an error or an illegal action counts as
  check, or fold if check is not legal. Uploads are the bot's directory,
  up to 1 MB zipped. Bots run with the Python standard library only, no
  network and no file writes.

actions
  ("fold",)
  ("check",)
  ("call",)
  ("raise", n)    n is your total bet this round, from min_raise to max_raise

state
  hand         hand number, from 1
  seat         your seat, 0-5
  button       button seat
  blinds       [small, big]
  hole         your two cards, e.g. ["As", "Td"]
  board        shared cards
  stacks       chips behind, by seat
  bets         chips bet this round, by seat
  pot          chips bet this hand
  to_call      chips needed to call
  legal        actions allowed now
  min_raise    smallest raise total, when raise is legal
  max_raise    all in, when raise is legal
  live         seats still in the hand
  actions      this hand so far, [cards on board, seat, action, bet this round]

cards
  ranks  23456789TJQKA
  suits  cdhs

game
  no-limit hold'em sit-and-go
  6 bots, new random table every game
  1,000 chips each
  blinds on hand n: n / 2n
  ends at last bot standing or 100 hands
  at 100 hands, places go by chips
  20 ms per decision, else check/fold
  up to 5 games a minute per bot
  paper tables are filled with house bots; live tables are 6 players

rating
  Elo, from 1500; each game counts as a win over every bot placed below

price
  paper   free, 1,000 games/day

  live*   buy-in   10¢
          pot      60¢
          1st      37¢
          2nd      20¢
          paid in  USDC on Solana

  * 18+, and only where paid skill competitions are allowed for you.
    deposits are held in our Solana wallets and tracked by us until you
    withdraw.

contact
  hello@pokerbots.dev
