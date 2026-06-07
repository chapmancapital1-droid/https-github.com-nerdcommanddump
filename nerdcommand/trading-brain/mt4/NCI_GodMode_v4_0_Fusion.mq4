//+------------------------------------------------------------------+
//|                                              NCI_GodMode_v4.mq4   |
//|             NERDCOMMAND Core Intelligence (NCI) - Autonomous EA   |
//|                                                                  |
//|  v4.0 FUSION - builds on v3.2, adds the live-bridge brain link   |
//|  and the profitability fixes from the 5-test audit:              |
//|                                                                  |
//|   [NEW] EMA 9/21/50 impulse gate (hard gate on GodMode port)     |
//|   [NEW] MACD-histogram expansion filter on main entries          |
//|   [NEW] OnTimer() heartbeat - dashboard refreshes between bars   |
//|   [NEW] Per-voter breakdown strings in NCI_LiveData.json         |
//|   [NEW] ReadCommandsJSON() - live overrides from the Python brain |
//|         (trading_enabled, min_confluence, risk_mult, block_until) |
//|   [NEW] Per-port win/loss tracking + auto-disable of bad ports   |
//|   [NEW] Max-daily-trades circuit breaker                          |
//|   [FIX] MinConfluence 6 -> 9   (was firing on 40% agreement)     |
//|   [FIX] M5 port R:R 0.45 -> 1.5 (was a losing-R config)          |
//|   [FIX] Zone port R:R 0.5 -> 1.5                                 |
//|   [FIX] QuickBE 0.25R -> 0.5R  (was BE'ing winners too early)    |
//|   [FIX] Secure trail now ATR-adaptive (was fixed 10p in noise)   |
//|                                                                  |
//|   All v3.2 logic, ports and stop manager are preserved intact.   |
//|                                                                  |
//|   *** RUN ON DEMO FIRST. Validate with Strategy Tester before    |
//|       any live capital. InpTradingEnabled gates execution. ***   |
//|                                                                  |
//|             (c) 2026 GangsterNerds LLC - NERDCOMMAND Trading      |
//+------------------------------------------------------------------+
#property copyright   "GangsterNerds LLC - NERDCOMMAND Trading"
#property version     "4.00"
#property description "NCI GodMode v4.0 Fusion - live-bridge brain link + impulse gate + per-port stats over the v3.2 multi-port engine."
#property strict

//================================================================
// MASTER SWITCH
//================================================================
extern string InpRunSect           = "=== MASTER ===";
extern bool   InpTradingEnabled    = true;    // false = report only (no OrderSend). Start TRUE on DEMO.
extern int    InpMagicNumber       = 24400;   // v4.0 magic (v3.2 was 24300)
extern double InpRiskPct           = 0.5;     // Risk per trade (% equity)
extern double InpFixedLots         = 0.0;
extern int    InpMaxSpreadPips     = 3;     // ".03" = 3-pip spread gate (entry + secure-trail)
extern int    InpMaxOpenTrades     = 1;
extern int    InpSlippage          = 3;

//--- Lot cap
extern double InpMaxLotsPerPipPctEquity = 0.1;
extern bool   InpEnforceLotCap     = true;

//================================================================
// ABC MARKET CYCLE - HARD GATE 0
//================================================================
extern string InpABCSect           = "=== ABC MARKET CYCLE ===";
extern bool   InpUseABCGate        = true;
extern int    InpABCAdxPeriod      = 14;
extern int    InpFERPeriod         = 10;      // bars for Fractal Efficiency Ratio
extern double InpStageA_AdxMax     = 20.0;    // ADX below this + low FER = consolidation
extern double InpStageA_FERMax     = 0.45;
extern double InpStageB_AdxMin     = 22.0;    // ADX above this + FER>=min = expansion
extern double InpStageB_FERMin     = 0.50;
extern double InpStageC_FERMax     = 0.55;
extern int    InpAdxRisingBars     = 3;       // ADX must exceed value N bars ago (block B3 exhaustion)
extern bool   InpUseHTFStage       = true;    // also require H4 not in Stage A

//================================================================
// ENTRY - confluence + indicators (v1.4 / v1.8)
//================================================================
extern string InpEntrySect         = "=== ENTRY ENGINE ===";
extern int    InpMinConfluence     = 9;       // of 15  (v3.2 was 6 - raised per audit)
extern int    InpDmaLength         = 25;
extern bool   InpRequireDmaSlope   = false;
extern int    InpStochK            = 25;
extern int    InpStochSmooth       = 3;
extern int    InpStochD            = 3;
extern int    InpStochBuyLo        = 30;
extern int    InpStochBuyHi        = 49;
extern int    InpStochSellLo       = 50;
extern int    InpStochSellHi       = 70;
extern int    InpStochRegimeMode   = 2;
extern int    InpStochAdxThresh    = 20;
extern bool   InpUseAEXD           = true;
extern int    InpDivLookback       = 5;
extern int    InpRsiLength         = 14;
extern bool   InpUseCandles        = true;
extern double InpPinTailFactor     = 2.5;
extern int    InpAtrPeriod         = 14;
extern double InpAtrMinPrice       = 0.0003;
extern bool   InpUseHTFTrend       = true;
extern int    InpHTFTimeframe      = PERIOD_H1;
extern int    InpHTFEmaLength      = 21;
extern int    InpHTFPersistBars    = 3;
extern bool   InpRequireHTFAgree   = true;
extern bool   InpRequireHTFSlope   = true;
extern int    InpHTFSlopeBars      = 3;
extern bool   InpHTFRequireBoth    = false;
extern bool   InpUseRobotrick      = true;
extern int    InpRoboFastLen       = 10;
extern int    InpRoboSlowLen       = 34;
extern double InpRoboChanAtrMult   = 0.5;
extern bool   InpUseVolumeFilter   = true;
extern int    InpVolumeAvgPeriod   = 20;
extern double InpVolumeMinRatio    = 1.0;
extern bool   InpUseMACDVoter      = true;
extern int    InpMacdFast          = 12;
extern int    InpMacdSlow          = 26;
extern int    InpMacdSignal        = 9;
extern bool   InpUseDayRangeVoter  = true;
extern double InpDayRangeZonePct   = 20.0;
extern bool   InpUseMTFVoter       = true;
extern int    InpMTFEmaFast        = 20;
extern int    InpMTFEmaSlow        = 50;
extern int    InpMTFMinAligned     = 2;
extern bool   InpUseTTFVoter       = true;
extern int    InpTTFBars           = 8;
extern bool   InpUseVegasH4        = true;
extern int    InpVegasFast         = 8;
extern int    InpVegasSlow         = 55;

//================================================================
// FUSION ENTRY PORTS - additive, does not remove GodMode core
//================================================================
extern string InpPortsSect          = "=== FUSION ENTRY PORTS ===";
extern bool   InpUseGodModePort     = true;    // Original ABC + 15-voter entry path
extern bool   InpUseHybridScalpPort = true;    // Hybrid v1.8 scalp path
extern bool   InpUseM5ArrowPort     = true;    // ScalpBot M5 arrow/cross path
extern bool   InpUseNeuroPorts      = true;    // NeuroTrick five entry methods
extern bool   InpUseZoneEntryPort   = true;    // High-WR DMA zone entry path
extern bool   InpABCBlocksAltPorts  = false;   // false keeps alt entry capacity even when ABC blocks main path
extern bool   InpRequireSecuredBeforeStack = true; // stack only after prior positions are protected

//--- Optional ADR exhaustion filter from Hybrid. Default OFF to avoid reducing entry capacity.
extern bool   InpUseADRFilter       = false;
extern int    InpADRPeriod          = 20;
extern double InpADRMaxPct          = 85.0;

//--- Hybrid scalp port
extern bool   InpScalpSessionOnly   = true;
extern int    InpScalpLonStart      = 7;
extern int    InpScalpLonEnd        = 10;
extern int    InpScalpNYStart       = 13;
extern int    InpScalpNYEnd         = 16;
extern int    InpScalpMinConfl      = 4;
extern int    InpScalpTPPips        = 10;
extern double InpScalpSLMult        = 1.0;
extern int    InpScalpMaxSpread     = 2;
extern int    InpScalpMaxTrades     = 2;

//--- M5 ScalpBot v2.0 port
extern int    InpM5MaxTrades        = 2;
extern bool   InpM5RequiresM5Chart  = false;  // false lets GodMode read PERIOD_M5 while attached to any chart
extern int    InpM5CooldownBars     = 2;
extern int    InpM5EntryFastEMA     = 9;
extern int    InpM5EntrySlowEMA     = 21;
extern int    InpM5CrossLookback    = 2;
extern bool   InpM5RequireEMAAlign  = true;
extern bool   InpM5UseWeeklyTrend   = false;
extern bool   InpM5UseDailyTrend    = false;
extern bool   InpM5UseH4Trend       = true;
extern bool   InpM5UseH1Trend       = true;
extern int    InpM5TrendFastEMA     = 20;
extern int    InpM5TrendSlowEMA     = 50;
extern int    InpM5RSIPeriod        = 14;
extern double InpM5RSIBullLevel     = 52.0;
extern double InpM5RSIBearLevel     = 48.0;
extern int    InpM5StochK           = 14;
extern int    InpM5StochD           = 3;
extern int    InpM5StochSlowing     = 3;
extern int    InpM5CCIPeriod        = 20;
extern double InpM5CCIBullLevel     = 50.0;
extern double InpM5CCIBearLevel     = -50.0;
extern int    InpM5MinConfluence    = 3;
extern bool   InpM5RequireCandle    = true;
extern bool   InpM5RequireArrows    = true;
extern bool   InpM5ExactArrowOnly   = false;
extern int    InpM5ArrowCount       = 2;
extern bool   InpM5UseSessionFilter = true;
extern int    InpM5GMTOffset        = 2;
extern bool   InpM5TradeTokyo       = false;
extern bool   InpM5TradeLondon      = true;
extern bool   InpM5TradeNY          = true;
extern int    InpM5MaxSpreadPoints  = 22;
extern int    InpM5MinATRPoints     = 10;
extern double InpM5StopATRMult      = 2.50;
extern double InpM5TakeProfitRR     = 1.50;   // v3.2 was 0.45 - raised to a winning R:R per audit
extern int    InpM5MinStopBufferPts = 10;

//--- NeuroTrick entry ports
extern int    InpNeuroMaxTrades       = 3;
extern bool   InpNeuro_AHSE           = true;
extern bool   InpNeuro_VolSpike       = true;
extern bool   InpNeuro_Engulfing      = true;
extern bool   InpNeuro_Pullback       = true;
extern bool   InpNeuro_CCI            = true;
extern int    InpNeuroFastEMA         = 20;
extern int    InpNeuroSlowEMA         = 50;
extern int    InpNeuroRSIPeriod       = 14;
extern double InpNeuroRSI_OB          = 65.0;
extern double InpNeuroRSI_OS          = 35.0;
extern int    InpNeuroCCIPeriod       = 20;
extern int    InpNeuroStochK          = 14;
extern int    InpNeuroStochD          = 3;
extern int    InpNeuroStochSlow       = 3;
extern int    InpNeuroMinConfluence   = 4;
extern int    InpNeuroVolumeLookback  = 20;
extern double InpNeuroVolumeSpikeMult = 1.8;
extern int    InpNeuroVolSpikeTF      = PERIOD_H4;
extern double InpNeuroSLAtrMult       = 1.5;
extern double InpNeuroRR              = 2.0;

//--- High win-rate DMA zone port
extern int    InpZoneMinScore       = 3;
extern double InpZoneBandAtrMult    = 0.5;
extern double InpZoneSLAtrMult      = 1.5;
extern double InpZoneRR             = 1.5;     // v3.2 was 0.5 - raised to a winning R:R per audit


//================================================================
// EXIT / STOP-LOSS MANAGEMENT
//================================================================
extern string InpExitSect          = "=== STOP-LOSS RULES ===";
extern double InpTPRRMultiplier    = 2.5;   // wider TP backstop; the trail is the real exit
extern double InpAdaptiveSlAtrMult = 1.2;
extern bool   InpUsePartialClose   = false;  // OFF: amputates winners (proven PF drag)
extern double InpTP1AtrMult        = 1.2;
extern double InpPartialPercent    = 35.0;
extern double InpBEPlusPips        = 2.0;
extern bool   InpUsePreBELock      = false;  // OFF: replaced by $-trigger trail
extern double InpPreBETriggerFrac  = 0.5;
extern double InpPreBESLFraction   = 0.5;
//--- Chandelier trail (v1.8) - Stage-aware multiplier
extern bool   InpUseChandelier     = false;  // OFF: replaced by secure trail
extern int    InpChanRange         = 15;      // swing lookback bars
extern double InpChanMultStageB    = 3.0;     // loose trail in expansion
extern double InpChanMultStageC    = 2.2;     // tight trail in contraction (PDF)
extern double InpTrailTriggerPips  = 7.0;
extern bool   InpUseSafeModify     = true;

//--- v3.1 SECURE + STACK  (+$ trigger -> trailing stop, then pyramid)
extern bool   InpUseSecureTrail    = true;   // arm a trailing stop once trade is +$ profit
extern double InpSecureProfitUSD   = 1.0;    // floating profit ($) that arms the trail
extern double InpSecureTrailPips   = 10.0;   // floor trail distance behind price (pips)
extern bool   InpSecureTrailUseAtr = true;   // v4.0: ATR-adaptive trail (widen with volatility)
extern double InpSecureTrailAtrMult= 1.5;    // v4.0: trail = max(SecureTrailPips, ATR*mult)
extern bool   InpUseStacking       = true;   // open a NEW entry once existing positions are secured
extern int    InpStackMaxTrades    = 3;      // max concurrent positions when stacking

//================================================================
// UNIFIED DYNAMIC STOP / PIP CATCHER
// One manager evaluates all stop candidates and only moves SL favorably.
//================================================================
extern string InpUnifiedStopSect    = "=== UNIFIED DYNAMIC STOP / PIP CATCHER ===";
extern bool   InpUseUnifiedStopManager = true;
extern double InpTrailMinStepPips   = 1.0;     // prevents modify floods
extern bool   InpUseQuickRBE        = true;    // quick break-even using original risk
extern double InpQuickBEAtR         = 0.50;    // v3.2 was 0.25 - raised so winners aren't BE'd too early
extern bool   InpUseRBasedATRTrail  = true;    // ATR trail after R threshold
extern double InpTrailAtR           = 0.55;
extern double InpRTrailAtrMult      = 0.55;
extern bool   InpUseHardLock        = true;    // Hybrid hard lock, routed through unified manager
extern double InpHardLockPips       = 15.0;
extern double InpHardLockPct        = 0.0;     // 0 = no partial, just protect with SL
extern double InpHardLockSLBuf      = 1.5;     // lock SL = entry +/- spread * buffer
extern bool   InpAllowReEntryAfterLock = true;
extern int    InpReEntryMaxPerBar   = 1;
extern bool   InpUseTimeStop        = false;
extern int    InpTimeStopBars       = 8;


//================================================================
// RISK GUARDS
//================================================================
extern string InpGuardSect         = "=== RISK GUARDS ===";
extern bool   InpUseStrikeCooldown = true;
extern int    InpStrikeLimit       = 3;
extern int    InpCooldownBars      = 24;
extern double InpPostCooldownRisk  = 0.5;
extern bool   InpUseDailyDDLock    = true;
extern double InpMaxDailyDDPct     = 3.0;
extern bool   InpUseSessionFilter  = true;
extern int    InpSessionStartHour  = 7;
extern int    InpSessionEndHour    = 20;
extern bool   InpSkipFriday        = false;

//================================================================
// v4.0 - EMA 9/21/50 IMPULSE GATE (NCI Companion logic)
//================================================================
extern string InpImpulseSect       = "=== v4.0 EMA IMPULSE GATE ===";
extern bool   InpUseEmaImpulseGate = true;    // hard gate on the GodMode main port
extern int    InpImpulseFastEMA    = 9;
extern int    InpImpulseMidEMA     = 21;
extern int    InpImpulseSlowEMA    = 50;
extern bool   InpImpulseRequireSlope = true;  // fast EMA must be rising (buy) / falling (sell)
extern int    InpImpulseSlopeBars  = 2;
extern bool   InpUseMacdHistFilter = true;    // require MACD histogram expanding in trade direction

//================================================================
// v4.0 - LIVE BRIDGE LINK (heartbeat + command override)
//================================================================
extern string InpBridgeSect        = "=== v4.0 LIVE BRIDGE ===";
extern bool   InpUseHeartbeat      = true;    // OnTimer writes dashboard between bars
extern int    InpHeartbeatSec      = 20;      // heartbeat interval (seconds)
extern bool   InpUseCommandFile    = true;    // read NCI_Commands.json overrides from the Python brain
extern string InpCommandFile       = "NCI_Commands.json";
extern string InpLiveDataFile      = "NCI_LiveData.json";
extern string InpSignalFile        = "signal_proposal.json";

//================================================================
// v4.0 - EXTRA RISK GUARDS
//================================================================
extern string InpGuard2Sect        = "=== v4.0 RISK GUARDS ===";
extern bool   InpUseMaxDailyTrades = true;
extern int    InpMaxDailyTrades    = 8;       // halt NEW entries after N trades/day
extern bool   InpUsePortAutoDisable= true;    // disable a port whose live stats turn bad
extern int    InpPortMinSample     = 20;      // closed trades before a port is auto-disable eligible
extern double InpPortMinWinRate    = 35.0;    // disable a port below this WR over its sample

//================================================================
// DASHBOARD / LOGGING
//================================================================
extern bool   InpWriteDashboard    = true;    // write JSON for GodMode dashboard
extern bool   InpVerboseLog        = true;
extern bool   InpLogConfluence     = true;

//================================================================
// GLOBALS
//================================================================
double   PipPoint, PipMultiplier;
datetime LastBarTime = 0;
int      ConsecutiveLosses = 0;
datetime CooldownUntilTime = 0;
int      PostCooldownTradesLeft = 0;
datetime DailyAnchorTime = 0;
double   DailyAnchorEquity = 0.0;
bool     DailyLocked = false;
int      TotalClosed=0, TotalWins=0, TotalLosses=0, LastTotalHistory=0;

//--- v4.0 runtime override + stats globals
int      g_minConfluence   = 9;     // seeded from InpMinConfluence in OnInit; bridge may override
bool     g_tradingEnabled  = true;  // seeded from InpTradingEnabled in OnInit; bridge may override
double   g_riskMult        = 1.0;   // bridge risk multiplier (0<rm<=3)
datetime g_blockUntil      = 0;     // bridge news/event blackout (server epoch); 0 = none
int      g_dailyTradeCount = 0;     // entries opened today
int      PortWins[11];              // indexed by PORT_* id
int      PortLosses[11];

#define TRACK_CAP 30
int  TrackTicket[TRACK_CAP];
int  TrackState [TRACK_CAP];
double TrackRiskPips[TRACK_CAP];
int  TrackPort  [TRACK_CAP];
int  TrackCount = 0;

#define TRK_PREBE     1
#define TRK_PARTIAL   2
#define TRK_HARDLOCK  4

#define PORT_NONE        0
#define PORT_GODMODE     1
#define PORT_HYBRIDSCALP 2
#define PORT_M5ARROW     3
#define PORT_NEURO_AHSE  4
#define PORT_NEURO_VOL   5
#define PORT_NEURO_ENG   6
#define PORT_NEURO_PULL  7
#define PORT_NEURO_CCI   8
#define PORT_ZONE        9
#define PORT_REENTRY     10

datetime g_lastM5EntryTime = 0;
bool     g_reentry_avail   = false;
int      g_reentry_dir     = 0;
datetime g_reentry_bar     = 0;
int      g_reentry_count   = 0;
string   g_lastEntryPort   = "NONE";

//================================================================
// INIT / UTILITY
//================================================================
void InitPipMath()
{
   int digits=(int)MarketInfo(Symbol(),MODE_DIGITS);
   if(digits==3||digits==5){ PipPoint=10*Point; PipMultiplier=10.0; }
   else                    { PipPoint=Point;    PipMultiplier=1.0;  }
}
bool IsNewBar(){ datetime t=iTime(Symbol(),Period(),0); if(t!=LastBarTime){ LastBarTime=t; return(true);} return(false); }
bool IsNewDay(){ if(DailyAnchorTime==0) return(true); return(TimeDay(TimeCurrent())!=TimeDay(DailyAnchorTime)||TimeMonth(TimeCurrent())!=TimeMonth(DailyAnchorTime)); }
void ResetDailyAnchor(){ DailyAnchorTime=TimeCurrent(); DailyAnchorEquity=AccountEquity(); DailyLocked=false; g_dailyTradeCount=0; }
double SpreadPips(){ return((Ask-Bid)/PipPoint); }
int CountMyTrades(){ int n=0; for(int i=OrdersTotal()-1;i>=0;i--){ if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue; if(OrderMagicNumber()==InpMagicNumber&&OrderSymbol()==Symbol()) n++; } return(n); }
bool InSession(){ if(!InpUseSessionFilter) return(true); int h=Hour(),dow=DayOfWeek(); if(InpSkipFriday&&dow==5) return(false); if(dow==0||dow==6) return(false); if(InpSessionStartHour<=InpSessionEndHour) return(h>=InpSessionStartHour&&h<InpSessionEndHour); return(h>=InpSessionStartHour||h<InpSessionEndHour); }
double NormalizeLots(double lots){ double mn=MarketInfo(Symbol(),MODE_MINLOT),mx=MarketInfo(Symbol(),MODE_MAXLOT),st=MarketInfo(Symbol(),MODE_LOTSTEP); if(st<=0) st=0.01; lots=MathFloor(lots/st)*st; if(lots<mn) lots=mn; if(lots>mx) lots=mx; return(NormalizeDouble(lots,2)); }
double ApplyLotCap(double l){ if(!InpEnforceLotCap) return(l); double pv=MarketInfo(Symbol(),MODE_TICKVALUE)*PipMultiplier; if(pv<=0) return(l); double maxD=AccountEquity()*InpMaxLotsPerPipPctEquity/100.0; double maxL=maxD/pv; if(l>maxL) return(NormalizeLots(maxL)); return(l); }
double CalcLots(double slDist){ if(InpFixedLots>0.0) return(ApplyLotCap(NormalizeLots(InpFixedLots))); if(slDist<=0.0) return(NormalizeLots(0.01)); double rm=(PostCooldownTradesLeft>0)?InpPostCooldownRisk:1.0; double rMoney=AccountEquity()*(InpRiskPct*rm*g_riskMult)/100.0; double tv=MarketInfo(Symbol(),MODE_TICKVALUE),ts=MarketInfo(Symbol(),MODE_TICKSIZE); if(ts==0) ts=Point; double vpl=(slDist/ts)*tv; if(vpl<=0) return(NormalizeLots(0.01)); return(ApplyLotCap(NormalizeLots(rMoney/vpl))); }

//================================================================
// INDICATOR SHORTHAND
//================================================================
double DmaHigh(int s){ return(iMA(NULL,0,InpDmaLength,0,MODE_SMA,PRICE_HIGH,s)); }
double DmaLow (int s){ return(iMA(NULL,0,InpDmaLength,0,MODE_SMA,PRICE_LOW, s)); }
double StochK (int s){ return(iStochastic(NULL,0,InpStochK,InpStochD,InpStochSmooth,MODE_SMA,0,MODE_MAIN,s)); }
double Rsi    (int s){ return(iRSI(NULL,0,InpRsiLength,PRICE_CLOSE,s)); }
double Atr    (int s){ return(iATR(NULL,0,InpAtrPeriod,s)); }
double Adx    (int s){ return(iADX(NULL,0,InpABCAdxPeriod,PRICE_CLOSE,MODE_MAIN,s)); }
double HtfEma (int s){ return(iMA(NULL,InpHTFTimeframe,InpHTFEmaLength,0,MODE_EMA,PRICE_CLOSE,s)); }
double HtfClose(int s){ return(iClose(NULL,InpHTFTimeframe,s)); }
double RoboFast(int s){ return(iMA(NULL,0,InpRoboFastLen,0,MODE_EMA,PRICE_CLOSE,s)); }
double RoboSlow(int s){ return(iMA(NULL,0,InpRoboSlowLen,0,MODE_EMA,PRICE_CLOSE,s)); }
double MTFEmaFast(int tf,int s){ return(iMA(NULL,tf,InpMTFEmaFast,0,MODE_EMA,PRICE_CLOSE,s)); }
double MTFEmaSlow(int tf,int s){ return(iMA(NULL,tf,InpMTFEmaSlow,0,MODE_EMA,PRICE_CLOSE,s)); }

double SpreadPoints(){ RefreshRates(); return((Ask-Bid)/Point); }

//----------------------------------------------------------------
// v4.0 EMA 9/21/50 impulse gate + MACD histogram filter
//----------------------------------------------------------------
double ImpEmaFast(int s){ return(iMA(NULL,0,InpImpulseFastEMA,0,MODE_EMA,PRICE_CLOSE,s)); }
double ImpEmaMid (int s){ return(iMA(NULL,0,InpImpulseMidEMA, 0,MODE_EMA,PRICE_CLOSE,s)); }
double ImpEmaSlow(int s){ return(iMA(NULL,0,InpImpulseSlowEMA,0,MODE_EMA,PRICE_CLOSE,s)); }

bool EmaImpulseBuy()
{
   if(!InpUseEmaImpulseGate) return(true);
   double c=iClose(NULL,0,1);
   bool stacked=(c>ImpEmaFast(1) && ImpEmaFast(1)>ImpEmaMid(1) && ImpEmaMid(1)>ImpEmaSlow(1));
   if(!stacked) return(false);
   if(InpImpulseRequireSlope && !(ImpEmaFast(1)>ImpEmaFast(1+InpImpulseSlopeBars))) return(false);
   return(true);
}
bool EmaImpulseSell()
{
   if(!InpUseEmaImpulseGate) return(true);
   double c=iClose(NULL,0,1);
   bool stacked=(c<ImpEmaFast(1) && ImpEmaFast(1)<ImpEmaMid(1) && ImpEmaMid(1)<ImpEmaSlow(1));
   if(!stacked) return(false);
   if(InpImpulseRequireSlope && !(ImpEmaFast(1)<ImpEmaFast(1+InpImpulseSlopeBars))) return(false);
   return(true);
}
double MacdHist(int s)
{
   double m =iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_MAIN,  s);
   double sg=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_SIGNAL,s);
   return(m-sg);
}
bool MacdHistBull(){ if(!InpUseMacdHistFilter) return(true); return(MacdHist(1)>MacdHist(2) && MacdHist(1)>0); }
bool MacdHistBear(){ if(!InpUseMacdHistFilter) return(true); return(MacdHist(1)<MacdHist(2) && MacdHist(1)<0); }

string PortName(int port)
{
   if(port==PORT_GODMODE)     return("GodMode15");
   if(port==PORT_HYBRIDSCALP) return("HybridScalp");
   if(port==PORT_M5ARROW)     return("M5ArrowCross");
   if(port==PORT_NEURO_AHSE)  return("Neuro_AHSE");
   if(port==PORT_NEURO_VOL)   return("Neuro_VolSpike");
   if(port==PORT_NEURO_ENG)   return("Neuro_Engulfing");
   if(port==PORT_NEURO_PULL)  return("Neuro_Pullback");
   if(port==PORT_NEURO_CCI)   return("Neuro_CCI");
   if(port==PORT_ZONE)        return("ZoneHighWR");
   if(port==PORT_REENTRY)     return("ReEntry");
   return("UNKNOWN");
}

//----------------------------------------------------------------
// v4.0 per-port stats + circuit breakers
//----------------------------------------------------------------
int PortIdFromComment(string c)
{
   if(StringFind(c,"GodMode15")>=0)       return(PORT_GODMODE);
   if(StringFind(c,"HybridScalp")>=0)     return(PORT_HYBRIDSCALP);
   if(StringFind(c,"M5ArrowCross")>=0)    return(PORT_M5ARROW);
   if(StringFind(c,"Neuro_AHSE")>=0)      return(PORT_NEURO_AHSE);
   if(StringFind(c,"Neuro_VolSpike")>=0)  return(PORT_NEURO_VOL);
   if(StringFind(c,"Neuro_Engulfing")>=0) return(PORT_NEURO_ENG);
   if(StringFind(c,"Neuro_Pullback")>=0)  return(PORT_NEURO_PULL);
   if(StringFind(c,"Neuro_CCI")>=0)       return(PORT_NEURO_CCI);
   if(StringFind(c,"ZoneHighWR")>=0)      return(PORT_ZONE);
   if(StringFind(c,"ReEntry")>=0)         return(PORT_REENTRY);
   return(PORT_NONE);
}
bool PortEnabled(int port)
{
   if(!InpUsePortAutoDisable) return(true);
   if(port<0 || port>10) return(true);
   int w=PortWins[port], l=PortLosses[port], n=w+l;
   if(n<InpPortMinSample) return(true);
   double wr=100.0*w/n;
   return(wr>=InpPortMinWinRate);
}
bool DailyTradeCapOK(){ if(!InpUseMaxDailyTrades) return(true); return(g_dailyTradeCount<InpMaxDailyTrades); }


//================================================================
// ABC MARKET CYCLE DETECTOR (Hard Gate 0)
// FER = |net move over N| / sum(|bar-to-bar move|)  (Kaufman efficiency)
//================================================================
double FER(int tf,int shift)
{
   double net = MathAbs(iClose(NULL,tf,shift) - iClose(NULL,tf,shift+InpFERPeriod));
   double path = 0;
   for(int j=0;j<InpFERPeriod;j++) path += MathAbs(iClose(NULL,tf,shift+j) - iClose(NULL,tf,shift+j+1));
   return(path>0 ? net/path : 0.0);
}

double AdxTF(int tf,int shift){ return(iADX(NULL,tf,InpABCAdxPeriod,PRICE_CLOSE,MODE_MAIN,shift)); }

// 0=Stage A, 1=Stage B, 2=Stage C
int DetectABCStage(int tf,int shift)
{
   double adx = AdxTF(tf,shift);
   double fer = FER(tf,shift);
   if(adx < InpStageA_AdxMax && fer < InpStageA_FERMax)  return(0); // A consolidation
   if(adx >= InpStageB_AdxMin && fer >= InpStageB_FERMin) return(1); // B expansion
   if(adx > InpStageA_AdxMax && adx < 25.0 && fer < InpStageC_FERMax) return(2); // C contraction
   return(adx >= 25.0 ? 1 : 0);
}

bool AdxRising(int tf,int shift){ return(AdxTF(tf,shift) > AdxTF(tf,shift+InpAdxRisingBars)); }

// Returns true only if it is SAFE to open a new entry (Stage B, B1/B2)
bool ABCAllowsEntry()
{
   if(!InpUseABCGate) return(true);
   int stage = DetectABCStage(0,1);
   if(stage != 1) return(false);                 // must be expansion
   if(!AdxRising(0,1)) return(false);             // block B3 exhaustion (ADX not rising)
   if(InpUseHTFStage && DetectABCStage(PERIOD_H4,1)==0) return(false); // H4 must not be dead range
   return(true);
}
bool ABCInContraction(){ return(InpUseABCGate && DetectABCStage(0,1)==2); }

string StageLabel(int s){ if(s==0) return("A_CONSOLIDATION"); if(s==1) return("B_EXPANSION"); if(s==2) return("C_CONTRACTION"); return("UNKNOWN"); }

//================================================================
// VOTERS (v1.4 + v1.8)
//================================================================
bool BullDivergence(){ if(!InpUseAEXD) return(true); int lb=InpDivLookback; double cur=iLow(NULL,0,iLowest(NULL,0,MODE_LOW,lb,1)); double prev=iLow(NULL,0,iLowest(NULL,0,MODE_LOW,lb,1+lb)); return(cur<prev && Rsi(1)>Rsi(1+lb)); }
bool BearDivergence(){ if(!InpUseAEXD) return(true); int lb=InpDivLookback; double cur=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,lb,1)); double prev=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,lb,1+lb)); return(cur>prev && Rsi(1)<Rsi(1+lb)); }
bool IsBullEngulf(){ double o0=iOpen(NULL,0,1),c0=iClose(NULL,0,1),o1=iOpen(NULL,0,2),c1=iClose(NULL,0,2); return(c0>o0&&c0>MathMax(o1,c1)&&o0<MathMin(o1,c1)); }
bool IsBearEngulf(){ double o0=iOpen(NULL,0,1),c0=iClose(NULL,0,1),o1=iOpen(NULL,0,2),c1=iClose(NULL,0,2); return(c0<o0&&c0<MathMin(o1,c1)&&o0>MathMax(o1,c1)); }
bool IsBullPin(){ double o=iOpen(NULL,0,1),c=iClose(NULL,0,1),l=iLow(NULL,0,1); double b=MathAbs(c-o); if(b<=0) return(false); return((MathMin(o,c)-l)>=InpPinTailFactor*b&&c>o); }
bool IsBearPin(){ double o=iOpen(NULL,0,1),c=iClose(NULL,0,1),h=iHigh(NULL,0,1); double b=MathAbs(c-o); if(b<=0) return(false); return((h-MathMax(o,c))>=InpPinTailFactor*b&&c<o); }
bool BullCandle(){ return(!InpUseCandles||IsBullEngulf()||IsBullPin()); }
bool BearCandle(){ return(!InpUseCandles||IsBearEngulf()||IsBearPin()); }
bool HtfTrendUpPersistent(){ if(!InpUseHTFTrend) return(true); for(int i=0;i<InpHTFPersistBars;i++) if(HtfClose(i)<=HtfEma(i)) return(false); return(true); }
bool HtfTrendDnPersistent(){ if(!InpUseHTFTrend) return(true); for(int i=0;i<InpHTFPersistBars;i++) if(HtfClose(i)>=HtfEma(i)) return(false); return(true); }
bool HtfSlopeUp(){ if(!InpUseHTFTrend||!InpRequireHTFSlope) return(true); return(HtfEma(0)>HtfEma(InpHTFSlopeBars)); }
bool HtfSlopeDn(){ if(!InpUseHTFTrend||!InpRequireHTFSlope) return(true); return(HtfEma(0)<HtfEma(InpHTFSlopeBars)); }
bool HTFGateAllowBuy(){ if(!InpRequireHTFAgree) return(true); bool p=HtfTrendUpPersistent(),s=HtfSlopeUp(); if(InpHTFRequireBoth) return(p&&s); return(p||s); }
bool HTFGateAllowSell(){ if(!InpRequireHTFAgree) return(true); bool p=HtfTrendDnPersistent(),s=HtfSlopeDn(); if(InpHTFRequireBoth) return(p&&s); return(p||s); }
bool VolumeAboveAvg(){ if(!InpUseVolumeFilter) return(true); double sum=0; for(int i=2;i<2+InpVolumeAvgPeriod;i++) sum+=(double)iVolume(NULL,0,i); double avg=sum/InpVolumeAvgPeriod; if(avg<=0) return(true); return((double)iVolume(NULL,0,1)>=avg*InpVolumeMinRatio); }
bool MacdBullCross(){ if(!InpUseMACDVoter) return(false); double mc=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_MAIN,1),mp=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_MAIN,2),sc=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_SIGNAL,1),sp=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_SIGNAL,2),mac=iMA(NULL,0,InpMacdSlow,0,MODE_EMA,PRICE_CLOSE,1),map=iMA(NULL,0,InpMacdSlow,0,MODE_EMA,PRICE_CLOSE,2); return(mc<0&&mc>sc&&mp<sp&&mac>map); }
bool MacdBearCross(){ if(!InpUseMACDVoter) return(false); double mc=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_MAIN,1),mp=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_MAIN,2),sc=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_SIGNAL,1),sp=iMACD(NULL,0,InpMacdFast,InpMacdSlow,InpMacdSignal,PRICE_CLOSE,MODE_SIGNAL,2),mac=iMA(NULL,0,InpMacdSlow,0,MODE_EMA,PRICE_CLOSE,1),map=iMA(NULL,0,InpMacdSlow,0,MODE_EMA,PRICE_CLOSE,2); return(mc>0&&mc<sc&&mp>sp&&mac<map); }
int DayRangePattern(){ if(!InpUseDayRangeVoter) return(0); double pH=iHigh(NULL,PERIOD_D1,1),pL=iLow(NULL,PERIOD_D1,1),pO=iOpen(NULL,PERIOD_D1,1),pC=iClose(NULL,PERIOD_D1,1); double rng=pH-pL; if(rng<Point*10) return(0); double z=rng*(InpDayRangeZonePct/100.0); if(((pH-pC)<=z)&&((pO-pL)<=z)) return(1); if(((pH-pO)<=z)&&((pC-pL)<=z)) return(-1); return(0); }
bool StochOkBuy(){ double k=StochK(1); int m=InpStochRegimeMode; if(m==2) m=(Adx(1)>=InpStochAdxThresh)?1:0; if(m==0) return(k>=InpStochBuyLo&&k<=InpStochBuyHi); return(k>=InpStochSellLo&&k<=InpStochSellHi); }
bool StochOkSell(){ double k=StochK(1); int m=InpStochRegimeMode; if(m==2) m=(Adx(1)>=InpStochAdxThresh)?1:0; if(m==0) return(k>=InpStochSellLo&&k<=InpStochSellHi); return(k>=InpStochBuyLo&&k<=InpStochBuyHi); }
bool MTFVoterBull(){ if(!InpUseMTFVoter) return(false); int a=0; if(MTFEmaFast(PERIOD_W1,0)>MTFEmaSlow(PERIOD_W1,0)) a++; if(MTFEmaFast(PERIOD_D1,0)>MTFEmaSlow(PERIOD_D1,0)) a++; if(MTFEmaFast(PERIOD_H4,0)>MTFEmaSlow(PERIOD_H4,0)) a++; if(MTFEmaFast(PERIOD_H1,0)>MTFEmaSlow(PERIOD_H1,0)) a++; return(a>=InpMTFMinAligned); }
bool MTFVoterBear(){ if(!InpUseMTFVoter) return(false); int a=0; if(MTFEmaFast(PERIOD_W1,0)<MTFEmaSlow(PERIOD_W1,0)) a++; if(MTFEmaFast(PERIOD_D1,0)<MTFEmaSlow(PERIOD_D1,0)) a++; if(MTFEmaFast(PERIOD_H4,0)<MTFEmaSlow(PERIOD_H4,0)) a++; if(MTFEmaFast(PERIOD_H1,0)<MTFEmaSlow(PERIOD_H1,0)) a++; return(a>=InpMTFMinAligned); }
bool TTFVoterBull(){ if(!InpUseTTFVoter) return(false); if(Bars<InpTTFBars*2+2) return(false); double bp=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,InpTTFBars,1))-iLow(NULL,0,iLowest(NULL,0,MODE_LOW,InpTTFBars,1+InpTTFBars)); double sp=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,InpTTFBars,1+InpTTFBars))-iLow(NULL,0,iLowest(NULL,0,MODE_LOW,InpTTFBars,1)); double d=0.5*(bp+sp); if(d<=0) return(false); return(((bp-sp)/d*100.0)>0); }
bool TTFVoterBear(){ if(!InpUseTTFVoter) return(false); if(Bars<InpTTFBars*2+2) return(false); double bp=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,InpTTFBars,1))-iLow(NULL,0,iLowest(NULL,0,MODE_LOW,InpTTFBars,1+InpTTFBars)); double sp=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,InpTTFBars,1+InpTTFBars))-iLow(NULL,0,iLowest(NULL,0,MODE_LOW,InpTTFBars,1)); double d=0.5*(bp+sp); if(d<=0) return(false); return(((bp-sp)/d*100.0)<0); }
bool VegasH4Bull(){ if(!InpUseVegasH4) return(false); double a=iMA(NULL,PERIOD_H4,InpVegasFast,0,MODE_SMA,PRICE_CLOSE,0),b=iMA(NULL,PERIOD_H4,InpVegasSlow,0,MODE_SMA,PRICE_CLOSE,0),c=iClose(NULL,PERIOD_H4,0); return(c>b&&a>b); }
bool VegasH4Bear(){ if(!InpUseVegasH4) return(false); double a=iMA(NULL,PERIOD_H4,InpVegasFast,0,MODE_SMA,PRICE_CLOSE,0),b=iMA(NULL,PERIOD_H4,InpVegasSlow,0,MODE_SMA,PRICE_CLOSE,0),c=iClose(NULL,PERIOD_H4,0); return(c<b&&a<b); }

//================================================================
// FUSION ENTRY PORT HELPERS
//================================================================
bool AltABCPortOK()
{
   if(!InpABCBlocksAltPorts) return(true);
   return(ABCAllowsEntry());
}

bool ADRExhausted()
{
   if(!InpUseADRFilter) return(false);
   double adr=0;
   for(int k=1;k<=InpADRPeriod;k++) adr += iHigh(NULL,PERIOD_D1,k)-iLow(NULL,PERIOD_D1,k);
   adr /= MathMax(1,InpADRPeriod);
   if(adr<=0) return(false);
   double today=iHigh(NULL,PERIOD_D1,0)-iLow(NULL,PERIOD_D1,0);
   bool exhausted=(today/adr >= InpADRMaxPct/100.0);
   if(exhausted && InpVerboseLog)
      Print("Fusion ADR exhausted: today=",DoubleToStr(today/PipPoint,0),"p ADR=",DoubleToStr(adr/PipPoint,0),"p");
   return(exhausted);
}

bool IsScalpSession()
{
   if(!InpScalpSessionOnly) return(true);
   int h=Hour();
   return((h>=InpScalpLonStart && h<InpScalpLonEnd) || (h>=InpScalpNYStart && h<InpScalpNYEnd));
}

bool ScalpCoreVotersBull()
{
   bool htfOk=HtfTrendUpPersistent();
   bool rsiOk=(Rsi(1)>Rsi(2));
   bool volOk=VolumeAboveAvg();
   if(InpVerboseLog && InpUseHybridScalpPort) Print("Fusion scalp bull core HTF=",htfOk," RSI=",rsiOk," VOL=",volOk);
   return(htfOk && rsiOk && volOk);
}

bool ScalpCoreVotersBear()
{
   bool htfOk=HtfTrendDnPersistent();
   bool rsiOk=(Rsi(1)<Rsi(2));
   bool volOk=VolumeAboveAvg();
   if(InpVerboseLog && InpUseHybridScalpPort) Print("Fusion scalp bear core HTF=",htfOk," RSI=",rsiOk," VOL=",volOk);
   return(htfOk && rsiOk && volOk);
}

int HybridScalpSignal(int buyScore,int sellScore)
{
   if(!InpUseHybridScalpPort) return(0);
   if(!AltABCPortOK()) return(0);
   if(!IsScalpSession()) return(0);
   if(SpreadPips()>InpScalpMaxSpread) return(0);
   if(buyScore>=InpScalpMinConfl && buyScore>sellScore && HTFGateAllowBuy() && ScalpCoreVotersBull()) return(1);
   if(sellScore>=InpScalpMinConfl && sellScore>buyScore && HTFGateAllowSell() && ScalpCoreVotersBear()) return(-1);
   return(0);
}

//------------------------- M5 ScalpBot port ------------------------
bool M5CooldownOK()
{
   if(g_lastM5EntryTime<=0) return(true);
   return((TimeCurrent()-g_lastM5EntryTime) >= InpM5CooldownBars*300);
}

bool M5IsTradingSession(datetime t)
{
   if(!InpM5UseSessionFilter) return(true);
   MqlDateTime dt;
   TimeToStruct(t + InpM5GMTOffset*3600, dt);
   int h=dt.hour;
   bool tok=InpM5TradeTokyo  && (h>=0  && h<9);
   bool lon=InpM5TradeLondon && (h>=8  && h<17);
   bool ny =InpM5TradeNY     && (h>=13 && h<22);
   return(tok||lon||ny);
}

int GetClosedTFShift(int tf, datetime bt)
{
   int s=iBarShift(NULL,tf,bt,false);
   int total=iBars(NULL,tf);
   if(s<0 || total<=0) return(-1);
   s=s+1;
   if(s>=total) return(-1);
   return(s);
}

void M5AddHTFVote(int tf,bool enabled,datetime bt,int &bScore,int &sScore)
{
   if(!enabled) return;
   int s=GetClosedTFShift(tf,bt);
   if(s<0) return;
   double fast=iMA(NULL,tf,InpM5TrendFastEMA,0,MODE_EMA,PRICE_CLOSE,s);
   double slow=iMA(NULL,tf,InpM5TrendSlowEMA,0,MODE_EMA,PRICE_CLOSE,s);
   if(fast>slow) bScore++; else sScore++;
}

bool M5CheckTrendTF(int tf,int direction,datetime bt)
{
   int s=GetClosedTFShift(tf,bt);
   if(s<0) return(false);
   double fast=iMA(NULL,tf,InpM5TrendFastEMA,0,MODE_EMA,PRICE_CLOSE,s);
   double slow=iMA(NULL,tf,InpM5TrendSlowEMA,0,MODE_EMA,PRICE_CLOSE,s);
   if(direction>0) return(fast>slow);
   return(fast<slow);
}

bool M5HTFTrendAligned(int direction,datetime bt)
{
   if(InpM5UseWeeklyTrend && !M5CheckTrendTF(PERIOD_W1,direction,bt)) return(false);
   if(InpM5UseDailyTrend  && !M5CheckTrendTF(PERIOD_D1,direction,bt)) return(false);
   if(InpM5UseH4Trend     && !M5CheckTrendTF(PERIOD_H4,direction,bt)) return(false);
   if(InpM5UseH1Trend     && !M5CheckTrendTF(PERIOD_H1,direction,bt)) return(false);
   return(true);
}

void M5ComputeSignalScores(int shift,int &bScore,int &sScore,bool &sessionOK,bool &bullPA,bool &bearPA)
{
   bScore=0; sScore=0;
   datetime bt=iTime(NULL,PERIOD_M5,shift);
   if(bt<=0){ sessionOK=false; bullPA=false; bearPA=false; return; }
   M5AddHTFVote(PERIOD_W1,InpM5UseWeeklyTrend,bt,bScore,sScore);
   M5AddHTFVote(PERIOD_D1,InpM5UseDailyTrend,bt,bScore,sScore);
   M5AddHTFVote(PERIOD_H4,InpM5UseH4Trend,bt,bScore,sScore);
   M5AddHTFVote(PERIOD_H1,InpM5UseH1Trend,bt,bScore,sScore);
   double rsi=iRSI(NULL,PERIOD_M5,InpM5RSIPeriod,PRICE_CLOSE,shift);
   if(rsi>InpM5RSIBullLevel) bScore++; else if(rsi<InpM5RSIBearLevel) sScore++;
   double stoch=iStochastic(NULL,PERIOD_M5,InpM5StochK,InpM5StochD,InpM5StochSlowing,MODE_SMA,0,MODE_MAIN,shift);
   if(stoch>50.0) bScore++; else sScore++;
   double cci=iCCI(NULL,PERIOD_M5,InpM5CCIPeriod,PRICE_TYPICAL,shift);
   if(cci>InpM5CCIBullLevel) bScore++; else if(cci<InpM5CCIBearLevel) sScore++;
   sessionOK=!InpM5UseSessionFilter || M5IsTradingSession(bt);
   bool bullC=(iClose(NULL,PERIOD_M5,shift)>iOpen(NULL,PERIOD_M5,shift));
   bool bearC=(iClose(NULL,PERIOD_M5,shift)<iOpen(NULL,PERIOD_M5,shift));
   bool bullEng=false,bearEng=false;
   if(shift+1<iBars(NULL,PERIOD_M5))
   {
      bullEng=bullC && iClose(NULL,PERIOD_M5,shift)>iOpen(NULL,PERIOD_M5,shift+1) && iOpen(NULL,PERIOD_M5,shift)<iClose(NULL,PERIOD_M5,shift+1);
      bearEng=bearC && iClose(NULL,PERIOD_M5,shift)<iOpen(NULL,PERIOD_M5,shift+1) && iOpen(NULL,PERIOD_M5,shift)>iClose(NULL,PERIOD_M5,shift+1);
   }
   bullPA=(!InpM5RequireCandle || bullC || bullEng);
   bearPA=(!InpM5RequireCandle || bearC || bearEng);
}

bool M5DirectionalArrow(int shift,int direction)
{
   int b=0,s=0; bool sess=false,bpa=false,spa=false;
   M5ComputeSignalScores(shift,b,s,sess,bpa,spa);
   if(direction>0) return(sess && bpa && b>=InpM5MinConfluence);
   return(sess && spa && s>=InpM5MinConfluence);
}

bool M5HasRecentCross(int direction)
{
   for(int sh=1; sh<=InpM5CrossLookback; sh++)
   {
      if(sh+1>=iBars(NULL,PERIOD_M5)) break;
      double f1=iMA(NULL,PERIOD_M5,InpM5EntryFastEMA,0,MODE_EMA,PRICE_CLOSE,sh);
      double s1=iMA(NULL,PERIOD_M5,InpM5EntrySlowEMA,0,MODE_EMA,PRICE_CLOSE,sh);
      double f2=iMA(NULL,PERIOD_M5,InpM5EntryFastEMA,0,MODE_EMA,PRICE_CLOSE,sh+1);
      double s2=iMA(NULL,PERIOD_M5,InpM5EntrySlowEMA,0,MODE_EMA,PRICE_CLOSE,sh+1);
      if(direction>0 && f2<=s2 && f1>s1) return(true);
      if(direction<0 && f2>=s2 && f1<s1) return(true);
   }
   return(false);
}

bool M5EntryEMAAligned(int direction,int shift)
{
   double fast=iMA(NULL,PERIOD_M5,InpM5EntryFastEMA,0,MODE_EMA,PRICE_CLOSE,shift);
   double slow=iMA(NULL,PERIOD_M5,InpM5EntrySlowEMA,0,MODE_EMA,PRICE_CLOSE,shift);
   if(direction>0) return(fast>slow);
   return(fast<slow);
}

int M5ArrowSignal()
{
   if(!InpUseM5ArrowPort) return(0);
   if(InpM5RequiresM5Chart && Period()!=PERIOD_M5) return(0);
   if(!AltABCPortOK()) return(0);
   if(!M5CooldownOK()) return(0);
   if(iBars(NULL,PERIOD_M5)<300) return(0);
   datetime bt=iTime(NULL,PERIOD_M5,1);
   if(bt<=0 || !M5IsTradingSession(bt)) return(0);
   if(SpreadPoints()>InpM5MaxSpreadPoints) return(0);
   double atrPts=iATR(NULL,PERIOD_M5,InpAtrPeriod,1)/Point;
   if(atrPts<InpM5MinATRPoints) return(0);
   bool buyTrig=true,sellTrig=true;
   if(InpM5RequireArrows)
   {
      for(int a=0; a<InpM5ArrowCount; a++)
      {
         if(!M5DirectionalArrow(1+a,1)) buyTrig=false;
         if(!M5DirectionalArrow(1+a,-1)) sellTrig=false;
      }
      if(InpM5ExactArrowOnly)
      {
         if(M5DirectionalArrow(1+InpM5ArrowCount,1)) buyTrig=false;
         if(M5DirectionalArrow(1+InpM5ArrowCount,-1)) sellTrig=false;
      }
   }
   else
   {
      buyTrig=M5DirectionalArrow(1,1);
      sellTrig=M5DirectionalArrow(1,-1);
   }
   bool buyCross=M5HasRecentCross(1);
   bool sellCross=M5HasRecentCross(-1);
   if(InpM5RequireEMAAlign)
   {
      buyCross=buyCross && M5EntryEMAAligned(1,1);
      sellCross=sellCross && M5EntryEMAAligned(-1,1);
   }
   bool buyReady=buyTrig && buyCross && M5HTFTrendAligned(1,bt);
   bool sellReady=sellTrig && sellCross && M5HTFTrendAligned(-1,bt);
   if(buyReady && !sellReady) return(1);
   if(sellReady && !buyReady) return(-1);
   return(0);
}

//------------------------- NeuroTrick ports ------------------------
int NeuroAHSESignal()
{
   int buy=0,sell=0;
   double w1f=iMA(NULL,PERIOD_W1,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), w1s=iMA(NULL,PERIOD_W1,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0); if(w1f>w1s) buy++; else sell++;
   double d1f=iMA(NULL,PERIOD_D1,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), d1s=iMA(NULL,PERIOD_D1,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0); if(d1f>d1s) buy++; else sell++;
   double h4f=iMA(NULL,PERIOD_H4,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), h4s=iMA(NULL,PERIOD_H4,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0); if(h4f>h4s) buy++; else sell++;
   double h1f=iMA(NULL,PERIOD_H1,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), h1s=iMA(NULL,PERIOD_H1,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0); if(h1f>h1s) buy++; else sell++;
   double rsi=iRSI(NULL,0,InpNeuroRSIPeriod,PRICE_CLOSE,1);
   if(rsi>50 && rsi<InpNeuroRSI_OB) buy++; else if(rsi<50 && rsi>InpNeuroRSI_OS) sell++;
   double st=iStochastic(NULL,0,InpNeuroStochK,InpNeuroStochD,InpNeuroStochSlow,MODE_SMA,0,MODE_MAIN,1);
   if(st>50 && st<80) buy++; else if(st<50 && st>20) sell++;
   double cf=iMA(NULL,0,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,1);
   double cs=iMA(NULL,0,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,1);
   if(buy>=InpNeuroMinConfluence && cf>cs) return(1);
   if(sell>=InpNeuroMinConfluence && cf<cs) return(-1);
   return(0);
}

int NeuroVolumeSpikeSignal()
{
   double avg=0;
   for(int v=1; v<=InpNeuroVolumeLookback; v++) avg+=(double)iVolume(NULL,InpNeuroVolSpikeTF,v);
   avg/=MathMax(1,InpNeuroVolumeLookback);
   double cur=(double)iVolume(NULL,InpNeuroVolSpikeTF,1);
   if(avg<=0 || cur<avg*InpNeuroVolumeSpikeMult) return(0);
   double d1f=iMA(NULL,PERIOD_D1,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), d1s=iMA(NULL,PERIOD_D1,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0);
   bool d1Bull=(d1f>d1s);
   bool spikeBull=(iClose(NULL,InpNeuroVolSpikeTF,1)>iOpen(NULL,InpNeuroVolSpikeTF,1));
   bool spikeBear=(iClose(NULL,InpNeuroVolSpikeTF,1)<iOpen(NULL,InpNeuroVolSpikeTF,1));
   double rsi=iRSI(NULL,0,InpNeuroRSIPeriod,PRICE_CLOSE,1);
   if(spikeBull && d1Bull && rsi<InpNeuroRSI_OB) return(1);
   if(spikeBear && !d1Bull && rsi>InpNeuroRSI_OS) return(-1);
   return(0);
}

int NeuroEngulfingSignal()
{
   if(Bars<3) return(0);
   double o1=Open[1],c1=Close[1],o2=Open[2],c2=Close[2];
   bool bull=(c1>o1)&&(c2<o2)&&(c1>o2)&&(o1<c2);
   bool bear=(c1<o1)&&(c2>o2)&&(c1<o2)&&(o1>c2);
   double rsi=iRSI(NULL,0,InpNeuroRSIPeriod,PRICE_CLOSE,1);
   double ema=iMA(NULL,0,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,1);
   double atr=Atr(1);
   bool nearEMA=(MathAbs(Close[1]-ema)<atr*0.5);
   double d1f=iMA(NULL,PERIOD_D1,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), d1s=iMA(NULL,PERIOD_D1,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0);
   bool d1Bull=(d1f>d1s);
   if(bull && rsi<45 && nearEMA && d1Bull) return(1);
   if(bear && rsi>55 && nearEMA && !d1Bull) return(-1);
   return(0);
}

int NeuroPullbackSignal()
{
   double fast=iMA(NULL,0,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,1);
   double slow=iMA(NULL,0,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,1);
   double atr=Atr(1);
   bool up=(fast>slow), dn=(fast<slow);
   bool buy=up && (Low[1]<fast+atr*0.3) && (Close[1]>fast) && (Close[1]>Open[1]);
   bool sell=dn && (High[1]>fast-atr*0.3) && (Close[1]<fast) && (Close[1]<Open[1]);
   double h4f=iMA(NULL,PERIOD_H4,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), h4s=iMA(NULL,PERIOD_H4,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0);
   bool h4Bull=(h4f>h4s);
   double rsi=iRSI(NULL,0,InpNeuroRSIPeriod,PRICE_CLOSE,1);
   if(buy && h4Bull && rsi>40 && rsi<65) return(1);
   if(sell && !h4Bull && rsi<60 && rsi>35) return(-1);
   return(0);
}

int NeuroCCISignal()
{
   double c1=iCCI(NULL,0,InpNeuroCCIPeriod,PRICE_TYPICAL,1);
   double c2=iCCI(NULL,0,InpNeuroCCIPeriod,PRICE_TYPICAL,2);
   bool bullCross=(c1>0 && c2<=0), bearCross=(c1<0 && c2>=0);
   double h4cci=iCCI(NULL,PERIOD_H4,InpNeuroCCIPeriod,PRICE_TYPICAL,1);
   double d1f=iMA(NULL,PERIOD_D1,InpNeuroFastEMA,0,MODE_EMA,PRICE_CLOSE,0), d1s=iMA(NULL,PERIOD_D1,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,0);
   bool d1Bull=(d1f>d1s);
   double sema=iMA(NULL,0,InpNeuroSlowEMA,0,MODE_EMA,PRICE_CLOSE,1);
   if(bullCross && h4cci>0 && d1Bull && Close[1]>sema) return(1);
   if(bearCross && h4cci<0 && !d1Bull && Close[1]<sema) return(-1);
   return(0);
}

int NeuroSignal(int &port)
{
   port=PORT_NONE;
   if(!InpUseNeuroPorts || !AltABCPortOK() || Bars<100) return(0);
   if(SpreadPips()>InpMaxSpreadPips) return(0);
   int s=0;
   if(InpNeuro_AHSE){ s=NeuroAHSESignal(); if(s!=0){ port=PORT_NEURO_AHSE; return(s); } }
   if(InpNeuro_VolSpike){ s=NeuroVolumeSpikeSignal(); if(s!=0){ port=PORT_NEURO_VOL; return(s); } }
   if(InpNeuro_Engulfing){ s=NeuroEngulfingSignal(); if(s!=0){ port=PORT_NEURO_ENG; return(s); } }
   if(InpNeuro_Pullback){ s=NeuroPullbackSignal(); if(s!=0){ port=PORT_NEURO_PULL; return(s); } }
   if(InpNeuro_CCI){ s=NeuroCCISignal(); if(s!=0){ port=PORT_NEURO_CCI; return(s); } }
   return(0);
}

//------------------------- High-WR zone port -----------------------
int ZoneBuyScore()
{
   int s=0;
   bool nearLow=(Ask<=DmaLow(1)+Atr(1)*InpZoneBandAtrMult);
   if(nearLow) s+=2;
   if(StochK(1)>=InpStochBuyLo && StochK(1)<=InpStochBuyHi) s++;
   if(!InpRequireDmaSlope || DmaHigh(1)>DmaHigh(4)) s++;
   if(Atr(1)>=InpAtrMinPrice) s++;
   return(s);
}

int ZoneSellScore()
{
   int s=0;
   bool nearHigh=(Bid>=DmaHigh(1)-Atr(1)*InpZoneBandAtrMult);
   if(nearHigh) s+=2;
   if(StochK(1)>=InpStochSellLo && StochK(1)<=InpStochSellHi) s++;
   if(!InpRequireDmaSlope || DmaLow(1)<DmaLow(4)) s++;
   if(Atr(1)>=InpAtrMinPrice) s++;
   return(s);
}

int ZoneEntrySignal()
{
   if(!InpUseZoneEntryPort || !AltABCPortOK()) return(0);
   if(SpreadPips()>InpMaxSpreadPips) return(0);
   int b=ZoneBuyScore(), s=ZoneSellScore();
   if(b>=InpZoneMinScore && b>s && HTFGateAllowBuy()) return(1);
   if(s>=InpZoneMinScore && s>b && HTFGateAllowSell()) return(-1);
   return(0);
}


//================================================================
// CONFLUENCE SCORE - v4.0 overloads emit a per-voter breakdown string
//================================================================
int BuyConfluenceScore(string &bd)
{
   int s=0; bd="";
   if(iClose(NULL,0,1)<=DmaLow(1)){ s++; bd+="DMA:1,"; } else bd+="DMA:0,";
   if(StochOkBuy()){ s++; bd+="Stoch:1,"; } else bd+="Stoch:0,";
   if(!InpRequireDmaSlope||(DmaHigh(1)>DmaHigh(4))){ s++; bd+="DmaSlope:1,"; } else bd+="DmaSlope:0,";
   if(BullDivergence()){ s++; bd+="Div:1,"; } else bd+="Div:0,";
   if(BullCandle()){ s++; bd+="Candle:1,"; } else bd+="Candle:0,";
   if(Atr(1)>=InpAtrMinPrice){ s++; bd+="Atr:1,"; } else bd+="Atr:0,";
   if(HtfTrendUpPersistent()){ s++; bd+="Htf:1,"; } else bd+="Htf:0,";
   if(!InpUseRobotrick||(RoboFast(1)>RoboSlow(1)+Atr(1)*InpRoboChanAtrMult)){ s++; bd+="Robo:1,"; } else bd+="Robo:0,";
   if(VolumeAboveAvg()){ s++; bd+="Vol:1,"; } else bd+="Vol:0,";
   if(Rsi(1)>Rsi(2)){ s++; bd+="Rsi:1,"; } else bd+="Rsi:0,";
   if(MacdBullCross()){ s++; bd+="Macd:1,"; } else bd+="Macd:0,";
   if(DayRangePattern()==1){ s++; bd+="DayRng:1,"; } else bd+="DayRng:0,";
   if(MTFVoterBull()){ s++; bd+="Mtf:1,"; } else bd+="Mtf:0,";
   if(TTFVoterBull()){ s++; bd+="Ttf:1,"; } else bd+="Ttf:0,";
   if(VegasH4Bull()){ s++; bd+="Vegas:1"; } else bd+="Vegas:0";
   return(s);
}
int SellConfluenceScore(string &bd)
{
   int s=0; bd="";
   if(iClose(NULL,0,1)>=DmaHigh(1)){ s++; bd+="DMA:1,"; } else bd+="DMA:0,";
   if(StochOkSell()){ s++; bd+="Stoch:1,"; } else bd+="Stoch:0,";
   if(!InpRequireDmaSlope||(DmaLow(1)<DmaLow(4))){ s++; bd+="DmaSlope:1,"; } else bd+="DmaSlope:0,";
   if(BearDivergence()){ s++; bd+="Div:1,"; } else bd+="Div:0,";
   if(BearCandle()){ s++; bd+="Candle:1,"; } else bd+="Candle:0,";
   if(Atr(1)>=InpAtrMinPrice){ s++; bd+="Atr:1,"; } else bd+="Atr:0,";
   if(HtfTrendDnPersistent()){ s++; bd+="Htf:1,"; } else bd+="Htf:0,";
   if(!InpUseRobotrick||(RoboFast(1)<RoboSlow(1)-Atr(1)*InpRoboChanAtrMult)){ s++; bd+="Robo:1,"; } else bd+="Robo:0,";
   if(VolumeAboveAvg()){ s++; bd+="Vol:1,"; } else bd+="Vol:0,";
   if(Rsi(1)<Rsi(2)){ s++; bd+="Rsi:1,"; } else bd+="Rsi:0,";
   if(MacdBearCross()){ s++; bd+="Macd:1,"; } else bd+="Macd:0,";
   if(DayRangePattern()==-1){ s++; bd+="DayRng:1,"; } else bd+="DayRng:0,";
   if(MTFVoterBear()){ s++; bd+="Mtf:1,"; } else bd+="Mtf:0,";
   if(TTFVoterBear()){ s++; bd+="Ttf:1,"; } else bd+="Ttf:0,";
   if(VegasH4Bear()){ s++; bd+="Vegas:1"; } else bd+="Vegas:0";
   return(s);
}
int BuyConfluenceScore() { string d; return(BuyConfluenceScore(d)); }
int SellConfluenceScore(){ string d; return(SellConfluenceScore(d)); }

//================================================================
// SAFE ORDER MODIFY  (v1.4)
//================================================================
bool SafeOrderModify(int ticket,double price,double sl,double tp,datetime exp,color c=CLR_NONE)
{
   if(!InpUseSafeModify) return(OrderModify(ticket,price,NormalizeDouble(sl,Digits),NormalizeDouble(tp,Digits),exp,c));
   int digits=(int)MarketInfo(Symbol(),MODE_DIGITS);
   double point=MarketInfo(Symbol(),MODE_POINT),stop=MarketInfo(Symbol(),MODE_STOPLEVEL)*point,spr=MarketInfo(Symbol(),MODE_SPREAD)*point,minD=MathMax(stop,spr)+point;
   price=NormalizeDouble(price,digits); sl=NormalizeDouble(sl,digits); tp=NormalizeDouble(tp,digits);
   if(!OrderSelect(ticket,SELECT_BY_TICKET,MODE_TRADES)) return(false);
   double cur=(OrderType()==OP_BUY)?MarketInfo(Symbol(),MODE_BID):MarketInfo(Symbol(),MODE_ASK);
   if(sl>0){ if(OrderType()==OP_BUY&&(cur-sl)<minD) sl=NormalizeDouble(cur-minD,digits); if(OrderType()==OP_SELL&&(sl-cur)<minD) sl=NormalizeDouble(cur+minD,digits); }
   if(tp>0){ if(OrderType()==OP_BUY&&(tp-cur)<minD) tp=NormalizeDouble(cur+minD,digits); if(OrderType()==OP_SELL&&(cur-tp)<minD) tp=NormalizeDouble(cur-minD,digits); }
   if(MathAbs(sl-OrderStopLoss())<point&&MathAbs(tp-OrderTakeProfit())<point) return(true);
   return(OrderModify(ticket,price,sl,tp,exp,c));
}

//================================================================
// TRACKING
//================================================================
int FindTrackingIndex(int t){ for(int i=0;i<TrackCount;i++) if(TrackTicket[i]==t) return(i); return(-1); }

double RiskPipsFromOrder()
{
   if(OrderStopLoss()<=0) return(0.0);
   return(MathAbs(OrderOpenPrice()-OrderStopLoss())/PipPoint);
}

int EnsureTracking(int t)
{
   int i=FindTrackingIndex(t); if(i>=0) return(i);
   if(TrackCount>=TRACK_CAP)
   {
      for(int j=0;j<TrackCount-1;j++)
      {
         TrackTicket[j]=TrackTicket[j+1]; TrackState[j]=TrackState[j+1];
         TrackRiskPips[j]=TrackRiskPips[j+1]; TrackPort[j]=TrackPort[j+1];
      }
      TrackCount--;
   }
   TrackTicket[TrackCount]=t;
   TrackState[TrackCount]=0;
   TrackRiskPips[TrackCount]=0.0;
   TrackPort[TrackCount]=PORT_NONE;
   if(OrderSelect(t,SELECT_BY_TICKET,MODE_TRADES)) TrackRiskPips[TrackCount]=RiskPipsFromOrder();
   TrackCount++;
   return(TrackCount-1);
}

void SetTrackState(int t,int s){ int i=EnsureTracking(t); if(i>=0) TrackState[i]=s; }
int GetTrackState(int t){ int i=FindTrackingIndex(t); return(i>=0?TrackState[i]:0); }
void AddTrackFlag(int t,int flag){ int i=EnsureTracking(t); if(i>=0) TrackState[i]=TrackState[i]|flag; }
bool HasTrackFlag(int t,int flag){ int i=EnsureTracking(t); if(i<0) return(false); return((TrackState[i]&flag)!=0); }
double GetTrackRiskPips(int t){ int i=EnsureTracking(t); if(i<0) return(0.0); if(TrackRiskPips[i]<=0.0 && OrderSelect(t,SELECT_BY_TICKET,MODE_TRADES)) TrackRiskPips[i]=RiskPipsFromOrder(); return(TrackRiskPips[i]); }
int GetTrackPort(int t){ int i=EnsureTracking(t); return(i>=0?TrackPort[i]:PORT_NONE); }
void SetTrackPort(int t,int port){ int i=EnsureTracking(t); if(i>=0) TrackPort[i]=port; }

void CleanupTracking()
{
   for(int i=TrackCount-1;i>=0;i--)
   {
      bool open=false;
      if(OrderSelect(TrackTicket[i],SELECT_BY_TICKET,MODE_TRADES)) if(OrderCloseTime()==0) open=true;
      if(!open)
      {
         for(int j=i;j<TrackCount-1;j++)
         {
            TrackTicket[j]=TrackTicket[j+1]; TrackState[j]=TrackState[j+1];
            TrackRiskPips[j]=TrackRiskPips[j+1]; TrackPort[j]=TrackPort[j+1];
         }
         TrackCount--;
      }
   }
}
int FindRemainderTicket(datetime ot,double op,int oty){ for(int i=OrdersTotal()-1;i>=0;i--){ if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue; if(OrderMagicNumber()!=InpMagicNumber||OrderSymbol()!=Symbol()) continue; if(OrderType()!=oty||OrderOpenTime()!=ot) continue; if(MathAbs(OrderOpenPrice()-op)>MarketInfo(Symbol(),MODE_POINT)*2) continue; return(OrderTicket()); } return(-1); }

//================================================================
// SL/TP COMPUTE (v1.4 DMA + ATR guard, R:R)
//================================================================
void ComputeBuySLTP(double entry,double &sl,double &tp){ double atr=Atr(1); sl=DmaLow(1); double d=entry-sl; if(d<InpAtrMinPrice||d<=0) sl=entry-atr*InpAdaptiveSlAtrMult; tp=entry+(entry-sl)*InpTPRRMultiplier; }
void ComputeSellSLTP(double entry,double &sl,double &tp){ double atr=Atr(1); sl=DmaHigh(1); double d=sl-entry; if(d<InpAtrMinPrice||d<=0) sl=entry+atr*InpAdaptiveSlAtrMult; tp=entry-(sl-entry)*InpTPRRMultiplier; }

void ComputePortSLTP(int direction,int port,double entry,double &sl,double &tp)
{
   double atr=Atr(1);
   if(atr<=0) atr=Atr(0);
   if(port==PORT_HYBRIDSCALP || port==PORT_REENTRY)
   {
      if(direction>0){ sl=entry-atr*InpScalpSLMult; tp=entry+InpScalpTPPips*PipPoint; }
      else           { sl=entry+atr*InpScalpSLMult; tp=entry-InpScalpTPPips*PipPoint; }
      return;
   }
   if(port==PORT_M5ARROW)
   {
      double spreadPts=SpreadPoints();
      double atrPts=iATR(NULL,PERIOD_M5,InpAtrPeriod,1)/Point;
      double stopLvl=MarketInfo(Symbol(),MODE_STOPLEVEL);
      double freeze=MarketInfo(Symbol(),MODE_FREEZELEVEL);
      double minDist=MathMax(stopLvl,freeze)+2.0;
      double stopPts=MathMax((double)InpM5MinStopBufferPts,MathMax(spreadPts*1.5,atrPts*InpM5StopATRMult));
      stopPts=MathMax(stopPts,minDist);
      double tpPts=MathMax(stopPts*InpM5TakeProfitRR,minDist);
      if(direction>0){ sl=entry-stopPts*Point; tp=entry+tpPts*Point; }
      else           { sl=entry+stopPts*Point; tp=entry-tpPts*Point; }
      return;
   }
   if(port==PORT_NEURO_AHSE || port==PORT_NEURO_VOL || port==PORT_NEURO_ENG || port==PORT_NEURO_PULL || port==PORT_NEURO_CCI)
   {
      double d=atr*InpNeuroSLAtrMult;
      if(direction>0){ sl=entry-d; tp=entry+d*InpNeuroRR; }
      else           { sl=entry+d; tp=entry-d*InpNeuroRR; }
      return;
   }
   if(port==PORT_ZONE)
   {
      double d=atr*InpZoneSLAtrMult;
      if(direction>0){ sl=entry-d; tp=entry+d*InpZoneRR; }
      else           { sl=entry+d; tp=entry-d*InpZoneRR; }
      return;
   }
   if(direction>0) ComputeBuySLTP(entry,sl,tp); else ComputeSellSLTP(entry,sl,tp);
}

void TryOpenByPort(int direction,int port)
{
   RefreshRates();
   double entry=(direction>0)?Ask:Bid;
   double sl,tp;
   ComputePortSLTP(direction,port,entry,sl,tp);
   double slDist=(direction>0)?(entry-sl):(sl-entry);
   if(slDist<=0){ Print("Fusion ",PortName(port)," SL invalid, skip"); return; }
   double lots=CalcLots(slDist);
   double minDist=MathMax((double)MarketInfo(Symbol(),MODE_STOPLEVEL),(double)MarketInfo(Symbol(),MODE_FREEZELEVEL))*Point;
   if(minDist<=0) minDist=Point;
   if(direction>0)
   {
      if(entry-sl<minDist) sl=entry-minDist;
      if(tp-entry<minDist) tp=entry+minDist;
   }
   else
   {
      if(sl-entry<minDist) sl=entry+minDist;
      if(entry-tp<minDist) tp=entry-minDist;
   }
   int type=(direction>0)?OP_BUY:OP_SELL;
   color cc=(direction>0)?clrLime:clrRed;
   string cmt="NCI v4.0 "+PortName(port);
   int t=OrderSend(Symbol(),type,lots,entry,InpSlippage,NormalizeDouble(sl,Digits),NormalizeDouble(tp,Digits),cmt,InpMagicNumber,0,cc);
   if(t<0)
   {
      Print("Fusion ",PortName(port)," ",(direction>0?"BUY":"SELL")," failed err=",GetLastError());
      return;
   }
   Print("Fusion ",PortName(port)," ",(direction>0?"BUY":"SELL")," #",t," lots=",DoubleToStr(lots,2)," SL=",DoubleToStr(sl,Digits)," TP=",DoubleToStr(tp,Digits));
   if(PostCooldownTradesLeft>0) PostCooldownTradesLeft--;
   EnsureTracking(t);
   SetTrackPort(t,port);
   g_dailyTradeCount++;                       // v4.0: feed the daily-trades circuit breaker
   if(port==PORT_M5ARROW) g_lastM5EntryTime=TimeCurrent();
   g_lastEntryPort=PortName(port);
}

void TryOpenBuy(){ TryOpenByPort(1,PORT_GODMODE); }
void TryOpenSell(){ TryOpenByPort(-1,PORT_GODMODE); }

//================================================================
// PARTIAL CLOSE + BE LOCK (v1.4)
//================================================================
void ManagePartialClose()
{
   if(!InpUsePartialClose) return;
   double atr=Atr(1); if(atr<=0) return;
   double tp1=atr*InpTP1AtrMult, preTrig=tp1*InpPreBETriggerFrac;
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber()!=InpMagicNumber||OrderSymbol()!=Symbol()) continue;
      if(OrderType()!=OP_BUY&&OrderType()!=OP_SELL) continue;
      int ticket=OrderTicket(); bool isBuy=(OrderType()==OP_BUY);
      double entry=OrderOpenPrice(), cur=isBuy?Bid:Ask;
      double prof=isBuy?(cur-entry):(entry-cur);
      double oSL=OrderStopLoss(), oSLd=isBuy?(entry-oSL):(oSL-entry);
      int state=GetTrackState(ticket);
      if(InpUsePreBELock&&state<1&&prof>=preTrig&&prof<tp1)
      {
         double pSL=isBuy?(entry-oSLd*InpPreBESLFraction):(entry+oSLd*InpPreBESLFraction);
         bool imp=(isBuy&&pSL>oSL)||(!isBuy&&pSL<oSL);
         if(imp&&SafeOrderModify(ticket,entry,pSL,OrderTakeProfit(),0,clrOrange)){ SetTrackState(ticket,1); Print("v3 PRE-BE #",ticket); }
      }
      if(prof>=tp1&&state<2)
      {
         double cl=OrderLots(),st=MarketInfo(Symbol(),MODE_LOTSTEP),mn=MarketInfo(Symbol(),MODE_MINLOT); if(st<=0) st=0.01;
         double clo=MathFloor(cl*(InpPartialPercent/100.0)/st)*st, rem=NormalizeDouble(cl-clo,2);
         if(clo<mn||rem<mn){ SetTrackState(ticket,2); continue; }
         datetime ot=OrderOpenTime(); double op=entry,otp=OrderTakeProfit(); int oty=OrderType(); double cp=isBuy?Bid:Ask;
         if(OrderClose(ticket,clo,cp,InpSlippage,clrYellow))
         {
            Print("v3 PARTIAL ",DoubleToStr(clo,2),"/",DoubleToStr(cl,2));
            int rt=FindRemainderTicket(ot,op,oty);
            if(rt>0){ double be=isBuy?(op+InpBEPlusPips*PipPoint):(op-InpBEPlusPips*PipPoint); if(SafeOrderModify(rt,op,be,otp,0,clrAqua)) Print("v3 BE LOCK #",rt); SetTrackState(rt,2); }
            return;
         }
      }
   }
}

//================================================================
// CHANDELIER TRAIL - Stage-aware (v1.8 + ABC)
// Stage B: loose (3.0x). Stage C: tight (2.2x) to catch the peak.
//================================================================
void ManageChandelier()
{
   if(!InpUseChandelier) return;
   double atr=Atr(0); if(atr<=0) return;
   double mult = ABCInContraction() ? InpChanMultStageC : InpChanMultStageB;
   double hi = iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,InpChanRange,1));
   double lo = iLow (NULL,0,iLowest (NULL,0,MODE_LOW, InpChanRange,1));
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber()!=InpMagicNumber||OrderSymbol()!=Symbol()) continue;
      double op=OrderOpenPrice(),cSL=OrderStopLoss(),cTP=OrderTakeProfit();
      if(OrderType()==OP_BUY)
      {
         if((Bid-op)/PipPoint < InpTrailTriggerPips) continue;
         double nSL=hi-atr*mult;
         if(nSL>op && (cSL==0||nSL>cSL+Point)) SafeOrderModify(OrderTicket(),op,nSL,cTP,0,clrYellow);
      }
      else if(OrderType()==OP_SELL)
      {
         if((op-Ask)/PipPoint < InpTrailTriggerPips) continue;
         double nSL=lo+atr*mult;
         if(nSL<op && (cSL==0||nSL<cSL-Point)) SafeOrderModify(OrderTicket(),op,nSL,cTP,0,clrYellow);
      }
   }
}

//================================================================
// v3.1 SECURE TRAIL + PYRAMID  (v4.0: ATR-adaptive trail distance)
// At +$InpSecureProfitUSD floating (spread<=gate): arm a trailing
// stop. SL only moves favorably. Once a position is secured
// (risk pulled inside the trail) the entry engine may stack a new one.
//================================================================
void ManageSecureTrail()
{
   if(!InpUseSecureTrail) return;
   if(SpreadPips()>InpMaxSpreadPips) return;          // only manage when spread tight (.03 gate)
   double atr=Atr(1); if(atr<=0) atr=Atr(0);
   double trail=(InpSecureTrailUseAtr && atr>0)?MathMax(InpSecureTrailPips*PipPoint,atr*InpSecureTrailAtrMult):InpSecureTrailPips*PipPoint;
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber()!=InpMagicNumber||OrderSymbol()!=Symbol()) continue;
      if(OrderType()!=OP_BUY&&OrderType()!=OP_SELL) continue;
      double profitUSD=OrderProfit()+OrderSwap()+OrderCommission();
      if(profitUSD<InpSecureProfitUSD) continue;       // not armed until +$ profit
      double op=OrderOpenPrice(),cSL=OrderStopLoss(),cTP=OrderTakeProfit();
      if(OrderType()==OP_BUY)
      {
         double nSL=Bid-trail;
         if(cSL==0||nSL>cSL+Point) SafeOrderModify(OrderTicket(),op,nSL,cTP,0,clrAqua);
      }
      else
      {
         double nSL=Ask+trail;
         if(cSL==0||nSL<cSL-Point) SafeOrderModify(OrderTicket(),op,nSL,cTP,0,clrAqua);
      }
   }
}


//================================================================
// UNIFIED STOP MANAGER - one dynamic SL/pip-catching path
//================================================================
bool StopImproves(int type,double candidate,double current,double stepGate)
{
   if(candidate<=0) return(false);
   if(type==OP_BUY)  return(current<=0 || candidate>current+stepGate);
   if(type==OP_SELL) return(current<=0 || candidate<current-stepGate);
   return(false);
}

void FlagReEntry(int type)
{
   if(!InpAllowReEntryAfterLock) return;
   g_reentry_avail=true;
   g_reentry_dir=(type==OP_BUY)?1:-1;
   g_reentry_bar=Time[0];
   g_reentry_count=0;
}

void ManageUnifiedStops()
{
   double atr=Atr(1); if(atr<=0) atr=Atr(0); if(atr<=0) return;
   double stepGate=InpTrailMinStepPips*PipPoint;
   double hi=iHigh(NULL,0,iHighest(NULL,0,MODE_HIGH,InpChanRange,1));
   double lo=iLow(NULL,0,iLowest(NULL,0,MODE_LOW,InpChanRange,1));
   double chanMult=ABCInContraction()?InpChanMultStageC:InpChanMultStageB;

   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber()!=InpMagicNumber || OrderSymbol()!=Symbol()) continue;
      int type=OrderType();
      if(type!=OP_BUY && type!=OP_SELL) continue;

      int ticket=OrderTicket();
      EnsureTracking(ticket);
      bool isBuy=(type==OP_BUY);
      double entry=OrderOpenPrice(), curSL=OrderStopLoss(), curTP=OrderTakeProfit();
      double curPx=isBuy?Bid:Ask;
      double profitPips=isBuy?(Bid-entry)/PipPoint:(entry-Ask)/PipPoint;
      double profitPrice=isBuy?(curPx-entry):(entry-curPx);
      double riskPips=GetTrackRiskPips(ticket);
      double rNow=(riskPips>0)?profitPips/riskPips:0.0;
      double bestSL=curSL;
      bool hardLockPending=false;

      // Optional time stop for fast scalp ports, routed through the same manager.
      if(InpUseTimeStop && InpTimeStopBars>0)
      {
         int barsSince=iBarShift(NULL,Period(),OrderOpenTime(),false);
         if(barsSince>=InpTimeStopBars)
         {
            bool closed=false;
            if(isBuy) closed=OrderClose(ticket,OrderLots(),Bid,InpSlippage,clrAqua);
            else      closed=OrderClose(ticket,OrderLots(),Ask,InpSlippage,clrAqua);
            if(closed) { Print("Fusion TIME STOP #",ticket); return; }
         }
      }

      // Partial close at ATR target, if enabled. Existing default is false.
      if(InpUsePartialClose && !HasTrackFlag(ticket,TRK_PARTIAL))
      {
         double tp1=atr*InpTP1AtrMult;
         if(profitPrice>=tp1)
         {
            double curLots=OrderLots(), step=MarketInfo(Symbol(),MODE_LOTSTEP), minLot=MarketInfo(Symbol(),MODE_MINLOT);
            if(step<=0) step=0.01;
            double closeLots=MathFloor((curLots*InpPartialPercent/100.0)/step)*step;
            double remLots=NormalizeDouble(curLots-closeLots,2);
            if(closeLots>=minLot && remLots>=minLot)
            {
               datetime ot=OrderOpenTime(); double op=entry; int oty=type; double otp=curTP;
               bool ok=OrderClose(ticket,closeLots,isBuy?Bid:Ask,InpSlippage,clrYellow);
               if(ok)
               {
                  int rt=FindRemainderTicket(ot,op,oty);
                  if(rt>0)
                  {
                     double be=isBuy?(op+InpBEPlusPips*PipPoint):(op-InpBEPlusPips*PipPoint);
                     SafeOrderModify(rt,op,be,otp,0,clrAqua);
                     AddTrackFlag(rt,TRK_PARTIAL);
                  }
                  Print("Fusion PARTIAL #",ticket," closed=",DoubleToStr(closeLots,2));
                  return;
               }
            }
            AddTrackFlag(ticket,TRK_PARTIAL);
         }
      }

      // Hard lock: protects the trade and can open a re-entry slot.
      if(InpUseHardLock && !HasTrackFlag(ticket,TRK_HARDLOCK) && profitPips>=InpHardLockPips)
      {
         double lockBuffer=SpreadPips()*InpHardLockSLBuf*PipPoint;
         double lockSL=isBuy?(entry+lockBuffer):(entry-lockBuffer);
         if(StopImproves(type,lockSL,bestSL,0.0)) bestSL=lockSL;

         if(InpHardLockPct>0.0)
         {
            double lots=OrderLots(), step2=MarketInfo(Symbol(),MODE_LOTSTEP), min2=MarketInfo(Symbol(),MODE_MINLOT);
            if(step2<=0) step2=0.01;
            double close2=MathFloor((lots*InpHardLockPct/100.0)/step2)*step2;
            double rem2=NormalizeDouble(lots-close2,2);
            if(close2>=min2 && rem2>=min2)
            {
               datetime hot=OrderOpenTime(); double hop=entry; int hty=type; double htp=curTP;
               bool hok=OrderClose(ticket,close2,isBuy?Bid:Ask,InpSlippage,clrMagenta);
               if(hok)
               {
                  int rr=FindRemainderTicket(hot,hop,hty);
                  if(rr>0)
                  {
                     SafeOrderModify(rr,hop,lockSL,htp,0,clrMagenta);
                     AddTrackFlag(rr,TRK_HARDLOCK);
                     FlagReEntry(type);
                  }
                  Print("Fusion HARD LOCK partial #",ticket," profit=",DoubleToStr(profitPips,1),"p");
                  return;
               }
            }
         }
         hardLockPending=true;
      }

      // Pre-BE window from original GodMode.
      if(InpUsePreBELock && !HasTrackFlag(ticket,TRK_PREBE) && riskPips>0)
      {
         double tp1d=atr*InpTP1AtrMult;
         if(profitPrice>=tp1d*InpPreBETriggerFrac && profitPrice<tp1d)
         {
            double pre=isBuy?(entry-riskPips*PipPoint*InpPreBESLFraction):(entry+riskPips*PipPoint*InpPreBESLFraction);
            if(StopImproves(type,pre,bestSL,0.0)){ bestSL=pre; AddTrackFlag(ticket,TRK_PREBE); }
         }
      }

      // Quick R-based break-even from ScalpBot.
      if(InpUseQuickRBE && riskPips>0 && rNow>=InpQuickBEAtR)
      {
         double be=isBuy?(entry+InpBEPlusPips*PipPoint):(entry-InpBEPlusPips*PipPoint);
         if(StopImproves(type,be,bestSL,0.0)) bestSL=be;
      }

      // USD-trigger secure trail from GodMode v3.1 (v4.0: ATR-adaptive distance).
      if(InpUseSecureTrail && SpreadPips()<=InpMaxSpreadPips)
      {
         double pnl=OrderProfit()+OrderSwap()+OrderCommission();
         if(pnl>=InpSecureProfitUSD)
         {
            double tr=(InpSecureTrailUseAtr && atr>0)?MathMax(InpSecureTrailPips*PipPoint,atr*InpSecureTrailAtrMult):InpSecureTrailPips*PipPoint;
            double sSL=isBuy?(Bid-tr):(Ask+tr);
            if(StopImproves(type,sSL,bestSL,0.0)) bestSL=sSL;
         }
      }

      // R-trigger ATR trail from ScalpBot.
      if(InpUseRBasedATRTrail && riskPips>0 && rNow>=InpTrailAtR)
      {
         double rTrail=MathMax((double)InpM5MinStopBufferPts*Point, atr*InpRTrailAtrMult);
         double rSL=isBuy?(Bid-rTrail):(Ask+rTrail);
         if(StopImproves(type,rSL,bestSL,0.0)) bestSL=rSL;
      }

      // Chandelier swing trail, stage-aware from GodMode/Hybrid.
      if(InpUseChandelier && profitPips>=InpTrailTriggerPips)
      {
         double cSL=isBuy?(hi-atr*chanMult):(lo+atr*chanMult);
         if(StopImproves(type,cSL,bestSL,0.0)) bestSL=cSL;
      }

      if(StopImproves(type,bestSL,curSL,stepGate))
      {
         if(SafeOrderModify(ticket,entry,bestSL,curTP,0,clrAqua))
         {
            if(hardLockPending){ AddTrackFlag(ticket,TRK_HARDLOCK); FlagReEntry(type); }
            Print("Fusion STOP #",ticket," ",PortName(GetTrackPort(ticket))," SL->",DoubleToStr(bestSL,Digits)," profit=",DoubleToStr(profitPips,1),"p R=",DoubleToStr(rNow,2));
         }
      }
      else if(hardLockPending)
      {
         AddTrackFlag(ticket,TRK_HARDLOCK);
         FlagReEntry(type);
      }
   }
}

// true only if EVERY open position has risk pulled inside the trail (all secured)
bool AllMyPositionsSecured()
{
   int cnt=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber()!=InpMagicNumber||OrderSymbol()!=Symbol()) continue;
      if(OrderType()!=OP_BUY&&OrderType()!=OP_SELL) continue;
      cnt++;
      double op=OrderOpenPrice(),sl=OrderStopLoss();
      if(sl<=0) return(false);
      double riskPips=(OrderType()==OP_BUY)?(op-sl)/PipPoint:(sl-op)/PipPoint;
      if(riskPips>InpSecureTrailPips+0.5) return(false);  // this one not secured yet
   }
   return(cnt>0);
}

//================================================================
// EXPECTANCY + STRIKE COOLDOWN + DAILY DD (v1.4) + per-port stats (v4.0)
//================================================================
void UpdateExpectancyAndStrikes()
{
   int total=OrdersHistoryTotal(); if(total<=LastTotalHistory) return;
   for(int i=LastTotalHistory;i<total;i++)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_HISTORY)) continue;
      if(OrderMagicNumber()!=InpMagicNumber||OrderSymbol()!=Symbol()) continue;
      if(OrderType()!=OP_BUY&&OrderType()!=OP_SELL) continue;
      double pnl=OrderProfit()+OrderSwap()+OrderCommission(); TotalClosed++;
      int cport=PortIdFromComment(OrderComment());     // v4.0: route the result to its port's record
      if(cport>=0 && cport<=10){ if(pnl>0) PortWins[cport]++; else PortLosses[cport]++; }
      if(pnl>0){ TotalWins++; ConsecutiveLosses=0; }
      else { TotalLosses++; ConsecutiveLosses++; if(InpUseStrikeCooldown&&ConsecutiveLosses>=InpStrikeLimit){ CooldownUntilTime=TimeCurrent()+InpCooldownBars*Period()*60; PostCooldownTradesLeft=3; Print("*** v3 STRIKE COOLDOWN *** ",ConsecutiveLosses," losses"); ConsecutiveLosses=0; } }
      double wr=TotalClosed>0?(100.0*TotalWins/TotalClosed):0.0;
      Print("[NCI WR v4] pnl=",DoubleToStr(pnl,2)," port=",PortName(cport)," W=",TotalWins," L=",TotalLosses," WR=",DoubleToStr(wr,1),"%");
   }
   LastTotalHistory=total;
}
void CheckDailyDD()
{
   if(IsNewDay()) ResetDailyAnchor();
   if(!InpUseDailyDDLock||DailyAnchorEquity<=0) return;
   double dd=100.0*(DailyAnchorEquity-AccountEquity())/DailyAnchorEquity;
   if(dd>=InpMaxDailyDDPct&&!DailyLocked){ DailyLocked=true; Print("*** v3 DAILY DD LOCK *** ",DoubleToStr(dd,2),"%"); }
}


//================================================================
// ENTRY CAPACITY + MULTI-PORT SELECTOR
//================================================================
int EffectiveMaxOpenTrades()
{
   int m=InpMaxOpenTrades;
   if(InpUseStacking && InpStackMaxTrades>m) m=InpStackMaxTrades;
   if(InpUseHybridScalpPort && InpScalpMaxTrades>m) m=InpScalpMaxTrades;
   if(InpUseM5ArrowPort && InpM5MaxTrades>m) m=InpM5MaxTrades;
   if(InpUseNeuroPorts && InpNeuroMaxTrades>m) m=InpNeuroMaxTrades;
   return(m);
}

bool EntryCapacityOK()
{
   int openN=CountMyTrades();
   int maxN=EffectiveMaxOpenTrades();
   if(openN>=maxN) return(false);
   if(openN>0 && !InpUseStacking) return(false);
   if(openN>0 && InpRequireSecuredBeforeStack && !AllMyPositionsSecured())
   {
      if(InpVerboseLog) Print("Fusion skip: previous position not secured yet");
      return(false);
   }
   return(true);
}

bool TryReEntryPort(int buy,int sell)
{
   if(!InpAllowReEntryAfterLock || !g_reentry_avail) return(false);
   if(g_reentry_bar!=Time[0]){ g_reentry_avail=false; g_reentry_count=0; return(false); }
   if(g_reentry_count>=InpReEntryMaxPerBar){ g_reentry_avail=false; return(false); }
   int dir=g_reentry_dir;
   if(SpreadPips()>InpScalpMaxSpread) return(false);
   if(dir==1 && buy>=InpScalpMinConfl && ScalpCoreVotersBull())
   {
      TryOpenByPort(1,PORT_REENTRY);
      g_reentry_count++; g_reentry_avail=false;
      return(true);
   }
   if(dir==-1 && sell>=InpScalpMinConfl && ScalpCoreVotersBear())
   {
      TryOpenByPort(-1,PORT_REENTRY);
      g_reentry_count++; g_reentry_avail=false;
      return(true);
   }
   g_reentry_avail=false;
   return(false);
}

bool TryEntryPorts(int buy,int sell)
{
   if(!EntryCapacityOK()) return(false);
   if(!DailyTradeCapOK()) return(false);                 // v4.0: daily-trades circuit breaker
   if(InpUseADRFilter && ADRExhausted()) return(false);

   if(TryReEntryPort(buy,sell)) return(true);

   // Port 1: original GodMode main path + v4.0 EMA-impulse & MACD-hist hard gates.
   if(InpUseGodModePort && PortEnabled(PORT_GODMODE) && SpreadPips()<=InpMaxSpreadPips && ABCAllowsEntry())
   {
      if(buy>=g_minConfluence && buy>sell && EmaImpulseBuy() && MacdHistBull())
      {
         if(HTFGateAllowBuy()){ if(g_tradingEnabled) TryOpenByPort(1,PORT_GODMODE); else Print("Fusion REPORT would BUY GodMode score=",buy); return(true); }
      }
      if(sell>=g_minConfluence && sell>buy && EmaImpulseSell() && MacdHistBear())
      {
         if(HTFGateAllowSell()){ if(g_tradingEnabled) TryOpenByPort(-1,PORT_GODMODE); else Print("Fusion REPORT would SELL GodMode score=",sell); return(true); }
      }
   }
   else if(InpUseGodModePort && InpVerboseLog && (SpreadPips()>InpMaxSpreadPips || !ABCAllowsEntry()))
   {
      Print("Fusion main GodMode blocked: spread=",DoubleToStr(SpreadPips(),1)," stage=",StageLabel(DetectABCStage(0,1))," adx=",DoubleToStr(Adx(1),1)," fer=",DoubleToStr(FER(0,1),3));
   }

   // Port 2: Hybrid scalp mode.
   if(PortEnabled(PORT_HYBRIDSCALP))
   {
      int scalpSig=HybridScalpSignal(buy,sell);
      if(scalpSig!=0)
      {
         if(g_tradingEnabled) TryOpenByPort(scalpSig,PORT_HYBRIDSCALP); else Print("Fusion REPORT would ",(scalpSig>0?"BUY":"SELL")," HybridScalp");
         return(true);
      }
   }

   // Port 3: ScalpBot M5 arrow/cross.
   if(PortEnabled(PORT_M5ARROW))
   {
      int m5Sig=M5ArrowSignal();
      if(m5Sig!=0)
      {
         if(g_tradingEnabled) TryOpenByPort(m5Sig,PORT_M5ARROW); else Print("Fusion REPORT would ",(m5Sig>0?"BUY":"SELL")," M5Arrow");
         return(true);
      }
   }

   // Port 4: NeuroTrick methods.
   int neuroPort=PORT_NONE;
   int neuroSig=NeuroSignal(neuroPort);
   if(neuroSig!=0 && neuroPort!=PORT_NONE && PortEnabled(neuroPort))
   {
      if(g_tradingEnabled) TryOpenByPort(neuroSig,neuroPort); else Print("Fusion REPORT would ",(neuroSig>0?"BUY":"SELL")," ",PortName(neuroPort));
      return(true);
   }

   // Port 5: High-WR DMA zone entry.
   if(PortEnabled(PORT_ZONE))
   {
      int zoneSig=ZoneEntrySignal();
      if(zoneSig!=0)
      {
         if(g_tradingEnabled) TryOpenByPort(zoneSig,PORT_ZONE); else Print("Fusion REPORT would ",(zoneSig>0?"BUY":"SELL")," ZoneHighWR");
         return(true);
      }
   }

   return(false);
}

//================================================================
// v4.0 - LIVE BRIDGE: read runtime overrides from the Python brain
// Minimal string-scan JSON reader (no library dependency).
//================================================================
string ReadFileText(string fname)
{
   int h=FileOpen(fname,FILE_READ|FILE_TXT,0);
   if(h==INVALID_HANDLE) return("");
   string s="";
   while(!FileIsEnding(h)) s+=FileReadString(h);
   FileClose(h);
   return(s);
}
double JsonNum(string js,string key,double def)
{
   string pat="\""+key+"\"";
   int p=StringFind(js,pat,0);
   if(p<0) return(def);
   p=StringFind(js,":",p);
   if(p<0) return(def);
   p++;
   int n=StringLen(js);
   while(p<n){ int cc=StringGetChar(js,p); if(cc==' '||cc=='\t'||cc=='\"') p++; else break; }
   string num="";
   while(p<n)
   {
      int c=StringGetChar(js,p);
      if((c>='0'&&c<='9')||c=='-'||c=='+'||c=='.'||c=='e'||c=='E'){ num=num+CharToStr((uchar)c); p++; }
      else break;
   }
   if(StringLen(num)==0) return(def);
   return(StrToDouble(num));
}
bool JsonBool(string js,string key,bool def)
{
   string pat="\""+key+"\"";
   int p=StringFind(js,pat,0);
   if(p<0) return(def);
   p=StringFind(js,":",p);
   if(p<0) return(def);
   int pt=StringFind(js,"true",p);
   int pf=StringFind(js,"false",p);
   if(pt>=0 && (pf<0 || pt<pf)) return(true);
   if(pf>=0) return(false);
   return(def);
}
void ReadCommandsJSON()
{
   if(!InpUseCommandFile) return;
   string js=ReadFileText(InpCommandFile);
   if(StringLen(js)<2) return;
   g_tradingEnabled = JsonBool(js,"trading_enabled",InpTradingEnabled);
   int mc=(int)JsonNum(js,"min_confluence",g_minConfluence);
   if(mc>=1 && mc<=15) g_minConfluence=mc;
   double rm=JsonNum(js,"risk_mult",g_riskMult);
   if(rm>0.0 && rm<=3.0) g_riskMult=rm;
   double bu=JsonNum(js,"block_until",0);   // server epoch seconds; 0 = no blackout
   g_blockUntil=(bu>0)?(datetime)bu:0;
}

//================================================================
// DASHBOARD JSON  (v4.0: voter breakdown + gate states + heartbeat)
//================================================================
void WriteDashboard(int buy,int sell)
{
   if(!InpWriteDashboard) return;
   string bbd="", sbd="";
   BuyConfluenceScore(bbd);
   SellConfluenceScore(sbd);
   int stage=DetectABCStage(0,1); int stageH4=DetectABCStage(PERIOD_H4,1);
   double bal=AccountBalance(),eq=AccountEquity(),mg=AccountMargin(),dd=(bal>0)?(eq-bal)/bal:0.0;
   bool emaB=EmaImpulseBuy(), emaS=EmaImpulseSell();
   string j="{";
   j+="\"version\": \"4.00\",";
   j+="\"symbol\": \""+Symbol()+"\",";
   j+="\"balance\": "+DoubleToStr(bal,2)+",";
   j+="\"equity\": "+DoubleToStr(eq,2)+",";
   j+="\"margin\": "+DoubleToStr(mg,2)+",";
   j+="\"drawdown\": "+DoubleToStr(dd,4)+",";
   j+="\"trades_open\": "+IntegerToString(CountMyTrades())+",";
   j+="\"trades_daily\": "+IntegerToString(g_dailyTradeCount)+",";
   j+="\"consec_losses\": "+IntegerToString(ConsecutiveLosses)+",";
   j+="\"phase\": \""+StageLabel(stage)+"\",";
   j+="\"abc_stage\": "+IntegerToString(stage)+",";
   j+="\"abc_stage_h4\": "+IntegerToString(stageH4)+",";
   j+="\"adx\": "+DoubleToStr(Adx(1),1)+",";
   j+="\"fer\": "+DoubleToStr(FER(0,1),3)+",";
   j+="\"buy_score\": "+IntegerToString(buy)+",";
   j+="\"sell_score\": "+IntegerToString(sell)+",";
   j+="\"min_confluence\": "+IntegerToString(g_minConfluence)+",";
   j+="\"buy_breakdown\": \""+bbd+"\",";
   j+="\"sell_breakdown\": \""+sbd+"\",";
   j+="\"ema_impulse_buy\": "+(emaB?"true":"false")+",";
   j+="\"ema_impulse_sell\": "+(emaS?"true":"false")+",";
   j+="\"macd_hist\": "+DoubleToStr(MacdHist(1),6)+",";
   j+="\"trading_enabled\": "+(g_tradingEnabled?"true":"false")+",";
   j+="\"risk_mult\": "+DoubleToStr(g_riskMult,2)+",";
   j+="\"atr\": "+DoubleToStr(Atr(1),6)+",";
   j+="\"timestamp\": \""+TimeToStr(TimeCurrent(),TIME_DATE)+" "+TimeToStr(TimeCurrent(),TIME_SECONDS)+"\"";
   j+="}";
   int h=FileOpen(InpLiveDataFile,FILE_WRITE|FILE_TXT,0); if(h!=INVALID_HANDLE){ FileWriteString(h,j); FileClose(h); }

   bool isBuy=buy>=sell; int sc=isBuy?buy:sell; string act=isBuy?"BUY":"SELL";
   string vbd=isBuy?bbd:sbd;
   bool emaGate=isBuy?emaB:emaS;
   bool macdGate=isBuy?MacdHistBull():MacdHistBear();
   double entry=isBuy?Ask:Bid,sl,tp; if(isBuy) ComputeBuySLTP(entry,sl,tp); else ComputeSellSLTP(entry,sl,tp);
   double slP=MathAbs(entry-sl)/PipPoint, tpP=MathAbs(tp-entry)/PipPoint, rr=(slP>0)?tpP/slP:0.0;
   bool qual=(sc>=g_minConfluence)&&ABCAllowsEntry()&&emaGate&&macdGate;
   string s="{";
   s+="\"symbol\": \""+Symbol()+"\",";
   s+="\"action\": \""+act+"\",";
   s+="\"mode\": \""+StageLabel(stage)+"\",";
   s+="\"godmode_score\": "+DoubleToStr(sc/15.0*10.0,2)+",";
   s+="\"confluence\": "+IntegerToString(sc)+",";
   s+="\"confluence_max\": 15,";
   s+="\"min_confluence\": "+IntegerToString(g_minConfluence)+",";
   s+="\"voter_breakdown\": \""+vbd+"\",";
   s+="\"ema_gate\": "+(emaGate?"true":"false")+",";
   s+="\"macd_gate\": "+(macdGate?"true":"false")+",";
   s+="\"abc_stage\": \""+StageLabel(stage)+"\",";
   s+="\"sl_pips\": "+DoubleToStr(slP,0)+",";
   s+="\"tp_pips\": "+DoubleToStr(tpP,0)+",";
   s+="\"risk_reward\": "+DoubleToStr(rr,2)+",";
   s+="\"qualifies\": "+(qual?"true":"false")+",";
   s+="\"timestamp\": \""+TimeToStr(TimeCurrent(),TIME_DATE)+" "+TimeToStr(TimeCurrent(),TIME_SECONDS)+"\",";
   s+="\"approved\": false";
   s+="}";
   int h2=FileOpen(InpSignalFile,FILE_WRITE|FILE_TXT,0); if(h2!=INVALID_HANDLE){ FileWriteString(h2,s); FileClose(h2); }
}

//================================================================
// LIFECYCLE
//================================================================
int OnInit()
{
   InitPipMath(); ResetDailyAnchor(); LastTotalHistory=OrdersHistoryTotal(); TrackCount=0;
   g_reentry_avail=false; g_reentry_count=0; g_lastM5EntryTime=0; g_lastEntryPort="NONE";
   g_minConfluence=InpMinConfluence; g_tradingEnabled=InpTradingEnabled; g_riskMult=1.0; g_blockUntil=0; g_dailyTradeCount=0;
   for(int pi=0;pi<11;pi++){ PortWins[pi]=0; PortLosses[pi]=0; }
   Print("===== NCI GodMode v4.0 FUSION - AUTONOMOUS EA =====");
   Print("Account: ",AccountNumber()," Bal: ",AccountBalance()," ",AccountCompany());
   Print("Symbol: ",Symbol()," TF: ",Period()," | TradingEnabled=",InpTradingEnabled);
   Print("ABC Gate=",InpUseABCGate," | MinConfluence=",InpMinConfluence,"/15 | Risk=",InpRiskPct,"% | R:R=",InpTPRRMultiplier,"x");
   Print("v4.0 GATES: EMAimpulse=",InpUseEmaImpulseGate," (",InpImpulseFastEMA,"/",InpImpulseMidEMA,"/",InpImpulseSlowEMA,") MACDhist=",InpUseMacdHistFilter);
   Print("v4.0 BRIDGE: heartbeat=",InpUseHeartbeat,"@",InpHeartbeatSec,"s cmdFile=",InpUseCommandFile," (",InpCommandFile,")");
   Print("v4.0 GUARDS: maxDailyTrades=",InpMaxDailyTrades," portAutoDisable=",InpUsePortAutoDisable," (n>=",InpPortMinSample," wr<",InpPortMinWinRate,"%)");
   Print("v4.0 FUSION PORTS: main=",InpUseGodModePort," scalp=",InpUseHybridScalpPort," m5=",InpUseM5ArrowPort," neuro=",InpUseNeuroPorts," zone=",InpUseZoneEntryPort," altABCBlock=",InpABCBlocksAltPorts);
   Print("v4.0 UNIFIED STOP: ",InpUseUnifiedStopManager," secure=",InpUseSecureTrail," (ATRtrail=",InpSecureTrailUseAtr," x",InpSecureTrailAtrMult,") quickR=",InpQuickBEAtR," trailR=",InpTrailAtR," hardLock=",InpHardLockPips,"p | STACK max=",EffectiveMaxOpenTrades());
   if(!InpTradingEnabled) Print(">>> REPORT-ONLY MODE: no orders will be placed. <<<");
   if(InpUseCommandFile) ReadCommandsJSON();
   WriteDashboard(BuyConfluenceScore(),SellConfluenceScore());
   if(InpUseHeartbeat && InpHeartbeatSec>0) EventSetTimer(InpHeartbeatSec);
   Print("===== v4.0 FUSION READY =====");
   return(INIT_SUCCEEDED);
}
void OnDeinit(const int reason){ EventKillTimer(); double wr=TotalClosed>0?(100.0*TotalWins/TotalClosed):0.0; Print("=== v4 stopped. WR ",TotalWins,"/",TotalClosed,"=",DoubleToStr(wr,2),"% ==="); }

// v4.0 heartbeat: keep the bridge fresh between bars + pull live overrides.
void OnTimer()
{
   if(InpUseCommandFile) ReadCommandsJSON();
   WriteDashboard(BuyConfluenceScore(),SellConfluenceScore());
}

void OnTick()
{
   // One manager owns dynamic stop-loss and pip catching.
   if(InpUseUnifiedStopManager) ManageUnifiedStops();
   else
   {
      ManagePartialClose();
      ManageChandelier();
      ManageSecureTrail();
   }
   UpdateExpectancyAndStrikes();
   CheckDailyDD();
   CleanupTracking();

   if(!IsNewBar()) return;

   if(InpUseCommandFile) ReadCommandsJSON();   // pull live overrides from the Python brain each bar

   int buy=BuyConfluenceScore(), sell=SellConfluenceScore();
   WriteDashboard(buy,sell);

   if(DailyLocked){ if(InpVerboseLog) Print("Fusion skip: daily DD locked"); return; }
   if(TimeCurrent()<CooldownUntilTime){ if(InpVerboseLog) Print("Fusion skip: cooldown"); return; }
   if(g_blockUntil>0 && TimeCurrent()<g_blockUntil){ if(InpVerboseLog) Print("Fusion skip: bridge blackout until ",TimeToStr(g_blockUntil,TIME_SECONDS)); return; }
   if(!DailyTradeCapOK()){ if(InpVerboseLog) Print("Fusion skip: daily trade cap ",g_dailyTradeCount,"/",InpMaxDailyTrades); return; }
   if(!InSession()) return;
   if(SpreadPips()>InpMaxSpreadPips && !InpUseM5ArrowPort && !InpUseHybridScalpPort)
   {
      if(InpVerboseLog) Print("Fusion skip: spread ",DoubleToStr(SpreadPips(),1));
      return;
   }

   if(InpLogConfluence)
      Print("Fusion scores BUY=",buy,"/15 SELL=",sell,"/15 conf>=",g_minConfluence," stage=",StageLabel(DetectABCStage(0,1))," lastPort=",g_lastEntryPort);

   if(!TryEntryPorts(buy,sell) && InpVerboseLog)
      Print("Fusion no trade: main=",MathMax(buy,sell),"/15, alt ports scanned, capacity=",CountMyTrades(),"/",EffectiveMaxOpenTrades());
}
//+------------------------------------------------------------------+
