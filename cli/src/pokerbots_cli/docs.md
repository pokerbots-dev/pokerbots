pokerbots.dev

start
  pb login                   sign in with GitHub
  pb logout                  sign out; keeps your wallet
  pb whoami                  who you are logged in as
  pb init mybot              create mybot/bot.py
  pb test [dir]              100 local games vs house bots, run as on the servers
  pb upload [dir]            upload a new version: v1, v2, ...
  pb deploy v1 --paper       play free games with v1
  pb deploy v1 --live        play for money with v1
  pb stop --paper|--live     stop playing; queued games still play
  pb status                  versions, rating, balance, recent games
  pb games [-n 100]          past games in a pager; --paper or --live
  pb watch                   the same, refreshed every 5 seconds
  pb top [--live]            leaderboard: rating order, 20+ games; live shows won
  pb history                 download your finished games, see history below
  pb docs [--plain]          show this
  pb upgrade                 upgrade pb

money
  pb wallet                  your Solana wallet address and balance
  pb deposit 5               move $5 USDC from your wallet to your balance
  pb withdraw 5              move $5 back to your wallet
  pb ledger                  every deposit, withdrawal, buy-in and prize

  Your wallet key is ~/.config/pokerbots/wallet.json and never leaves your
  machine. Send USDC on Solana to its address, then deposit. We pay the
  network fees. Withdrawals go to the wallet you last deposited from.
  Large withdrawals may wait for review.

bot.py
  class Bot:
      def act(self, state):
          if "check" in state["legal"]:
              return ("check",)
          return ("fold",)

  A new Bot is created for every game. act is called for every decision.
  Each decision gets 20 ms of CPU time, and must reply within 100 ms.
  A late reply, an error or an illegal action counts as check, or fold
  if check is not legal. Uploads are the bot's directory, up to 5 MB
  zipped. Bots run with the Python standard library only, no network and
  no file writes; pb test runs them the same way.

  Loading bot.py and Bot() get 5 seconds that do not count against the
  20 ms: build or load lookup tables there.

actions
  ("fold",)
  ("check",)
  ("call",)
  ("raise", n)    n is your total bet this round, from min_raise to max_raise

state
  hand          hand number, from 1
  hands_left    hands until the game ends at 100
  street        preflop, flop, turn or river
  seat          your seat, 0-5
  players       login by seat, or "house"
  button        button seat
  small_blind   small blind seat
  big_blind     big blind seat
  blinds        [small, big] amounts
  hole          your two cards, e.g. ["As", "Td"]
  board         shared cards
  stacks_start  chips by seat when this hand began
  stacks        chips behind, by seat
  bets          chips bet this round, by seat
  current_bet   the bet to match this round
  pot           chips bet this hand
  to_call       chips needed to call
  legal         actions allowed now
  min_raise     smallest raise total, when raise is legal
  max_raise     all in, when raise is legal
  live          seats still in the hand
  all_in        seats in the hand with no chips behind
  out           eliminated seats, first out first
  actions       this hand so far, [cards on board, seat, action, bet this round]
  past          finished hands this game: hand, board, shown (cards by seat,
                null unless shown down), won (chips by seat)

cards
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
  20 ms CPU per decision, else check/fold
  up to 5 games a minute per bot
  paper tables are filled with house bots; live tables are 6 players

rating
  Elo, from 1500; each game counts as a win over every bot placed below

history
  pb history [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--paper|--live] [--all] [-o dir]

  One JSON line per finished game, one file per day: history/2026-10-29.jsonl.
  Games appear 10 minutes after they end. Default: your games, last 7 days.
  --all adds everyone's games. You see your own hole cards and any cards
  shown down; folded cards stay hidden. Re-running skips games you have.

  game   id, mode, finished_at, hands_played, you (your seat),
         players [seat, user, place, rating_change, won ($, live)],
         hands [hand, button, small_blind, big_blind, blinds, stacks_start,
                hole, board, actions, shown, won]

price
  paper   free, 1,000 games/day

  live*   buy-in   10¢
          pot      60¢
          1st      39¢
          2nd      20¢
          paid in  USDC on Solana

  * 18+, and only where paid skill competitions are allowed for you.
    deposits are held in our Solana wallets and tracked by us until you
    withdraw.

contact
  hello@pokerbots.dev
