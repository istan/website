+++
title = "The age of frivolous software"
date = "2026-11-01"
summary = "How AI changes the types of software we can build"
slug = "the-age-of-frivolous-software"
+++

Every four years I spend as much time as I can doing one thing: watching the World Cup.

Here I am with a friend on June 11th at the Berkeley Greek Theater watching an early group-stage game (South Korea defeated Czechia 2-1; a great game). James Blake is playing a concert somewhere out of frame to the right. 

![Watching a World Cup match at the Berkeley Greek Theater](/assets/frivolous-software-world-cup.png)

I love the sport and enthusiastically endorse its sometimes-sneered-at nickname, "the beautiful game", but, more than that, I *love* the World Cup and how it brings so much of the world together in (mostly) good-natured competitive revelry and celebration of national pride. It's a wonderful event and a great periodic reminder that we're all humans and can have fun together even when on opposing sides. People travel from around the world for it and I consistently meet and have more fun with strangers during the World Cup than at any other event in my life: it really is just peak humanity.

Concurrently with the start of the World Cup our friends at Anthropic were releasing their then-much-anticipated Fable 5 AI model which had, I was told, impressively strong coding abilities. My former employer, Stripe, had also just released [Stripe Projects](https://projects.dev/), a nifty-sounding tool for agentically provisioning web infrastructure. I wanted to try out these new devtools and was annoyed by the dearth of good World Cup websites (they all seemed to want to sell something to me) so I wondered: **can I use Fable + Projects to build the best (for me) World Cup website in the world?** And can I do it without writing any of the code myself or manually configuring any infrastructure? 

Turns out the answer was yes! I shipped the first version of [worldcupdash.com](https://worldcupdash.com/) on June 12th, one day after the World Cup opener and maybe 8 hours after contemplating doing it, and spent the next 6 weeks vibing away improvements while I watched and attended games. The site grew from 1 user (just me) to ~50k users in just a few weeks and I collected plenty of examples of people telling me that it was their favorite World Cup website and that they had become daily users. Pretty cool!

### What is it?

A live-updating, information-dense, no-bullshit[0] World Cup dashboard with scores, live match details, win probabilities, group standings, etc. 

![The World Cup dashboard showing matches and tournament standings](/assets/frivolous-software-dashboard.jpeg)
{:.compact-image}


I wanted it to be fast, mobile-friendly, easy to use and fun for users (me). It should never be annoying. I can look at it at any time and get a snapshot of how the tournament is going and what is upcoming.

It should also be easy for the maintainer (also me), i.e.:

- no dependencies
- no crazy build system, package.json, etc
- no backend
- runs entirely in a browser
- uses publicly available APIs
- deployed via Netlify, on a very cheap plan

With Fable and Projects I was able to launch a first version in just a few hours and with just a few prompts. Fable largely figured out the data sourcing and plumbing itself with little direction from me (there was more direction later as new features needed different data sources). Projects provisioned a Netlify account and gave the agent an auth token it could use to take actions in that account (like deploying the site). 

The initial site design came largely from Fable with me providing aesthetic direction and feedback/steering. Over the next six weeks I deployed the site hundreds of times, so the finished product was hardly a one-shot result. Getting the UI to be actually good rather than merely usable was the most fiddly part and where I spent the most time directing the agent.

I would add new features as they came to mind while watching games: "Another extra-time goal! I wish the dashboard tracked this." Or, as the tournament progressed, I would ship just-in-time features that were needed to keep pace with the tournament, e.g. when the group stage ends and knockout stage begins this implies a whole host of new features that I hadn't pre-built but was able to quickly add and deploy, sometimes within minutes of when I needed them. 

This was one of the most fun parts of the project: near-real-time discovery, implementation, and deployment of new features. Some of these were necessary features I hadn't thought of that, in the pre-AI (aka dinosaur) days, you might have carefully specified and scoped up front and had on a roadmap. Others were purely for fun, for example, one night while attending a game in Santa Clara a friend joked that the last time the Italians qualified for the Cup they were the Romans and every game was recorded in Roman numerals. I thought that was funny so I went home and had AI implement a "Roman" theme, which re-renders the dashboard in a travertine color scheme and replaces all the numbers with unintelligible Roman numerals. **There was no point to this other than to instantiate our joke about Italy's poor qualifying run into software: it was completely frivolous.** 


![The World Cup dashboard in its Roman theme](/assets/frivolous-software-roman.jpeg)
{:.compact-image}



In some sense this entire project was frivolous, and that's what's so great about it! Four years ago I would not have built World Cup Dash. I might have daydreamed about it, but I would have suffered through using the annoying-but-already-available and, on some deeply unsatisfying level, "good enough" websites because it would have been too costly in my time and brainpower to build a just-for-me, just-for-fun, entirely customized to my idiosyncrasies and sense of humor World Cup website. Even just setting up the infrastructure would have been annoying enough to block me. But, as of the 2026 World Cup (and surely more so now), the tools exist such that every fun web idea that you previously dismissed as frivolous and not worth the time is back on the table and, even if you're building purely for yourself, it might turn out 50,000 other people out there want what you have to offer. And how cool is that? We've entered the age of frivolous software, and I love it.

(And yes, eventually I added a playable NES-style penalty shoot-out game.)

![The dashboard’s retro football game showing Morocco scoring against the Netherlands](/assets/frivolous-software-finale.jpeg)
{:.compact-image}

[0] well, a little bullshit but it was always for fun and hidden behind a click or two.
