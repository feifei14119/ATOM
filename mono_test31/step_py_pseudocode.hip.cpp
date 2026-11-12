// 仅包含原 step.py 的 body (L214-L475) 的 HIP/C++ 风格解释性伪代码。
// PY Lx-Ly 对应 atom/models/deepseek_v41/mono/gfx1250/kernels/step.py。
// step.py SHA256: 1ef733d1ed0664a3a0618e53e05d9779b44825686bcf6225373d0a64dbd9d7d1
// if constexpr / for_constexpr 表示 tracing 条件/展开；普通 if/for 表示设备运行时逻辑。
// u64 参数承载设备虚拟地址，scale 是数值；这里的 u64 别名表示 64-bit 无符号整数。
// TR/TRD/NL/NDR/rank/part/SEGS/L/LD/stx/keyed 来自原 build 闭包，不是额外 kernel 参数。
// Context、with_fields、make_* 简写 dict/LazyC/cwith 的参数构造，来源行号在调用处标明。
// fptr/ltab/entry_front 等保留为外部 helper 调用；不展开 build、launch 或 helper 定义。
// 这是解释性伪代码，不能直接编译；?: 表示值选择，不规定后端指令或求值方式。

__global__ void body(
    u64 recv0,   // 当前 GPU 可访问的 TP rank 0 接收缓冲区基址
    u64 recv1,   // 当前 GPU 可访问的 TP rank 1 接收缓冲区基址
    u64 recv2,   // 当前 GPU 可访问的 TP rank 2 接收缓冲区基址
    u64 recv3,   // 当前 GPU 可访问的 TP rank 3 接收缓冲区基址
    u64 cnt,     // 本 decode step 的同步计数器区基址，host 按 step 清零
    u64 st,      // 时间戳缓冲区基址：每 CTA 32 个 8-byte 槽
    float scale, // attention softmax 的数值缩放系数
    u64 fp,      // 主体设备表基址：FPTRS、ATAB、每层 LKEYS 行
    u64 tp       // 尾部设备指针表基址：head / sampling / verify / draft 使用
) { // PY L214-L216；参数含义另见原 launch 注释 L480-L481
    Array<u64, 4> recv = {recv0, recv1, recv2, recv3}; // PY L217
    hx.TOFLAG[0] = fptr(fp, "cyc");                 // PY L218，tracing 侧设定 timeout counter 指针
    auto [active_recv, tep] = tp_epoch_begin(recv, fp, rank); // PY L219
    recv = active_recv;

    for_constexpr (int si = 0; si < size(SEGS); ++si) { // PY L220，segment 在 tracing 时展开
        constexpr auto [seg_lo, seg_hi, seg_kind] = SEGS[si]; // PY L221
        constexpr bool DRS = (seg_kind & 4) != 0;    // PY L222，kind 1=target，4=draft
        constexpr int FIRST_LY = -1;               // PY L223

        if constexpr (si == 0 && part != "draft") { // PY L224-L227，target 入口
            int t = thread_id(), b = logical_cta_id(); // PY L228-L229
            u64 sm = lds_base();                   // PY L230
            u64 TCNT = cnt + i64(NL + NDR) * LCB;   // PY L231
            CX.stage_block_state(make_block_state_context(fp, t, b, aid=fptr(fp, "tids")), TR, 1); // PY L232-L234
            handoff(TCNT + LY.TARGET_STATE, t, false); // PY L235，全设备 handoff
            if (b < FS.FRONT_CTAS)                  // PY L236
                entry_front(fp, sm, b, TENTRY_ROW, FS.NE, FS.TOPK); // PY L237
            handoff(TCNT + LY.TARGET_FRONT, t, false); // PY L238
        }

        constexpr int TRx = DRS ? TRD : TR;         // PY L239
        auto Lx = DRS ? LD : L;                     // PY L240
        constexpr string DSUF = DRS ? "_d" : "";   // PY L241
        constexpr int RNE = DRS ? DRAFT_NE : FS.NE;
        constexpr int RTOPK = DRS ? DRAFT_TOPK : FS.TOPK; // PY L242

        if constexpr (DRS) {                       // PY L243
            int t = thread_id(), b = logical_cta_id(); // PY L244-L245
            u64 sm = lds_base();                   // PY L246
            u64 TCNT = cnt + i64(NL + NDR) * LCB;   // PY L247
            if constexpr (part == "all") {         // PY L248，target tail 原位置在 draft 入口内
                if (t == 0) gstore_u64(st + i64(b) * 256 + 25 * 8, clock64()); // PY L249-L250
                ST.target(tp, t, b, sm, st, TCNT, recv, rank,
                          head_d=4, ctx=fptr(fp, "ctxtab"), T=TR); // PY L251-L253
            }
            if (b == 0) {                          // PY L256，只让 CTA0 进入 metadata 工作
                CX.draft_meta(make_draft_meta_context(fp, tp, t), TRD / DSPARK_W, DSPARK_W); // PY L257-L259
            }
            CX.stage_block_state(make_block_state_context(fp, t, b, aid=ST.tptr(tp, "anc")),
                                 TRD / DSPARK_W, DSPARK_W); // PY L260-L262
            handoff(TCNT + LY.DRAFT_STATE, t, false); // PY L263
            if (b < FS.FRONT_CTAS)                  // PY L264
                entry_front(fp, sm, b, NL + NDR, DRAFT_NE, DRAFT_TOPK); // PY L265
            handoff(TCNT + LY.DRAFT_FRONT, t, false); // PY L266
        }

        for (int Ly = seg_lo; Ly < seg_hi; ++Ly) {   // PY L267，设备层循环，绝对层号
            constexpr int kind = seg_kind;         // PY L268
            int t = thread_id(), b = logical_cta_id(); // PY L269-L270
            int w = t / 32, l = t % 32;             // PY L271-L272
            u64 sm = lds_base();                    // PY L273
            u64 lc = cnt + i64(Ly) * LCB;           // PY L274
            auto c = make_attention_context(fp, Lx, Ly, tep, DSUF,
                                            t, b, w, l, sm, scale, stx, rank); // PY L277-L291
            u64 stp = st + i64(b) * 256;            // PY L292
            auto stamp = [=](constexpr int k) {     // PY L294
                if constexpr (k != 0 && k != 12 && k != 18) return; // PY L295-L296
                if (t == 0) gstore_u64(stp + k * 8, clock64()); // PY L297-L298
            };
            if (Ly == 0) stamp(0);                  // PY L300-L301
            if (Ly == 1) stamp(12);                 // PY L302-L303

            if constexpr ((kind & 1) != 0) {        // PY L304，target 编译变体
                if (ltab(fp, Ly, "lflags")() & 128)  // PY L305
                    ES.stage_engq(with_fields(c, engemb=ltab(fp,Ly,"engemb")(),
                                               eng8=fptr(fp,"eng8"), engs=fptr(fp,"engs"))); // PY L306
            }
            stage_A(c);                            // PY L307
            pf_rows(c["wqb"] + i64(b) * 16 * QL, QL, 16, QL, t); // PY L308
            pf_rows(c["wqb"] + i64(b + CTAS) * 16 * QL, QL, 16, QL, t); // PY L309
            handoff(lc, t, true);                   // PY L310
            if constexpr ((kind & 1) != 0) {        // PY L311
                if (ltab(fp, Ly, "lflags")() & 128)  // PY L312
                    ES.stage_engkv(with_fields(c, eng8=fptr(fp,"eng8"), engs=fptr(fp,"engs"),
                                                engw=ltab(fp,Ly,"engw")(), engws=ltab(fp,Ly,"engws")(),
                                                engkv=fptr(fp,"engkv"))); // PY L313-L314
            }
            stage_kv(c);                           // PY L315
            stage_C(c);                            // PY L316

            // C++ 风格预声明；原 Python 在下面的 target 分支内赋值，draft 不读取。
            bool isidx;                            // PY L318
            if constexpr ((kind & 1) != 0) {        // PY L317
                isidx = (ltab(fp, Ly, "lflags")() & 8) != 0; // PY L318
                if (isidx) {                       // PY L319
                    auto ci = with_fields(c, iqw=ltab(fp,Ly,"iqw")(), iqws=ltab(fp,Ly,"iqws")(),
                                             iww=ltab(fp,Ly,"iww")(), iq=fptr(fp,"iq"),
                                             iwp=fptr(fp,"iwp"), axn=fptr(fp,"axn")); // PY L320-L321
                    IS.stage_iq(ci);               // PY L322
                    IS.stage_iw(ci);               // PY L323
                    u64 lfl = ltab(fp, Ly, "lflags")(); // PY L324，保留原重新读表
                    bool hascomp = (lfl & 2) != 0;  // PY L325
                    bool r1 = (lfl & 4) != 0;       // PY L326
                    if (hascomp)                   // PY L327
                        CS.stage_cgemm(with_fields(c, cwkv=ltab(fp,Ly,"cwkv")(),
                                                     axn=fptr(fp,"axn"), cpart=fptr(fp,"cpart")), r1); // PY L328
                }
            }
            handoff(lc + LY.KV_C, t, true);         // PY L329，无条件执行

            if constexpr ((kind & 1) != 0) {        // PY L330，isidx 延续上面的 tracing 变量
                if (isidx) {                       // PY L331
                    IS.stage_iquant(with_fields(c, iq=fptr(fp,"iq"), iwp=fptr(fp,"iwp"),
                                                  iq_out=fptr(fp,"iq_out"), iqs_out=fptr(fp,"iqs_out"),
                                                  iw_out=fptr(fp,"iw_out"))); // PY L332-L333
                    u64 lfl2 = ltab(fp, Ly, "lflags")(); // PY L334
                    if (lfl2 & 2) {                // PY L335，compressor rows / ring
                        bool r1b = (lfl2 & 4) != 0; // PY L336
                        auto cc = make_compressor_context(c, fp, Ly); // PY L337-L342
                        CS.stage_crow(cc, r1b);     // PY L343
                        CS.stage_cring(cc, r1b);    // PY L344
                    }
                    handoff(lc + LY.INDEX_QUANT, t, true); // PY L345
                    if (ltab(fp, Ly, "ibat")() != 0) { // PY L346，完整 64-bit 值
                        auto cs = make_score_context(c, fp, Ly); // PY L348-L352
                        u64 lfl3 = ltab(fp, Ly, "lflags")(); // PY L353
                        bool isrx = (lfl3 & 64) != 0; // PY L354，REINDEX
                        cs = with_fields(cs, ibmax=ltab(fp,Ly,"ibmax")(), icand=ltab(fp,Ly,"icand")(),
                                             lvl=fptr(fp,"ilvl"), iprod=(lfl3 & 32) != 0, ts=None); // PY L355-L357
                        SC.stage_score_any(cs, isrx); // PY L359
                        handoff(lc + LY.SCORE, t, true); // PY L360
                        int npass = isrx ? IDX_LEVELS : (cs["iprod"] ? 2 * IDX_LEVELS : IDX_LEVELS); // PY L361
                        for (int pi = 0; pi < npass; ++pi) { // PY L362，当前为两遍或四遍
                            int pmode = isrx ? TK.MODE_RX : (pi < IDX_LEVELS ? TK.MODE_SEL : TK.MODE_BLK); // PY L363
                            int plev = pi % IDX_LEVELS; // PY L364
                            TK.stage_select_any(with_fields(cs, ts=None), plev, IDX_LEVELS, pmode); // PY L365
                            handoff(lc + LY.SELECT0 + i64(pi) * 4, t, true); // PY L366
                        }
                    }
                }
            }

            stage_D(c);                            // PY L367
            pf_rows(c["woa"] + i64(b/4)*32*KWOA + i64(b%4)*1024, KWOA, 32, 1024, t); // PY L368
            handoff(lc + LY.ATTN_D, t, true);        // PY L369
            stage_E(c);                            // PY L370
            pf_rows(c["wob"] + i64(b/4)*80*NWOA + i64(b%4)*512, NWOA, 80, 512, t); // PY L371
            handoff(lc + LY.ATTN_E, t, true);        // PY L372
            stage_F_cluster(c);                    // PY L373
            __syncthreads();                       // PY L374
            int par = Ly % 2;                      // PY L375
            tp_allreduce(with_fields(c, ytgt=fptr(fp,"y1")), par * 2, 2 * Ly + 1); // PY L376
            gpub(lc + LY.TP1_GROUPS, b, t);         // PY L377

            for (int hf = 0; hf < opaque_s(2); ++hf) { // PY L379，保留设备两遍循环
                if (hf == 0) iprefetch(28);         // PY L380-L381
                if (b < FS.FRONT_CTAS)              // PY L384，idle CTA 不进入此等待
                    gwait(lc + (hf == 0 ? LY.TP1_GROUPS : LY.TP2_GROUPS), b, t); // PY L385
                if (b < FS.FRONT_CTAS) {            // PY L386
                    bool isf = hf == 0;             // PY L387
                    auto fsel = [=](string n0, string n1) { // PY L389-L391
                        return fptr(fp, isf ? n0 : n1);
                    };
                    int tq = thread_id();          // PY L392
                    Context cu = make_front_base_context(tq, b, sm + FRONT_LDS_OFF,
                                                         rms_eps=D.RMS_EPS, hc_eps=1e-6, norm_eps=D.RMS_EPS); // PY L393
                    cu.update(R=fsel("R","Rout"), y=fsel("y1","y2"), pre=fsel("pre","npre"),
                              post=fsel("post","npost"), comb=fsel("comb","ncomb")); // PY L394-L395
                    cu.update(fnh=fsel("fnh","afnh"), fnl=fsel("fnl","afnl"), hsc=fsel("hsc","ahsc"),
                              hbs=fsel("hbs","ahbs"), nw=fsel("nw","anw"),
                              gate=fptr(fp,"gate"), gbias=fptr(fp,"gbias")); // PY L395-L397
                    cu["Rout"] = fsel("Rout","aRout"); // PY L399
                    bool segment_last = hf != 0 && Ly == (DRS ? NL + NDR - 1 : NL - 1);
                    cu["xn"] = segment_last ? (DRS ? ST.tptr(tp,"dh") : fptr(fp,"xh")) : fsel("xn","axn"); // PY L398-L399
                    cu.update(x8=isf ? fptr(fp,"fx8") : c["x8"], xs=isf ? fptr(fp,"fxs") : c["xs"],
                              part=fptr(fp,"part"), plog=fptr(fp,"plog"), cand=fptr(fp,"cand"), cands=fptr(fp,"cands")); // PY L399-L401
                    cu.update(npre=fsel("npre","anpre"), npost=fsel("npost","anpost"), ncomb=fsel("ncomb","ancomb"),
                              ids=fptr(fp,"ids"), wts=fptr(fp,"wts"), isffn=isf, xs32=hf != 0,
                              merge=isf, hdev=true, ne=RNE, topk=RTOPK); // PY L401-L403
                    // 用本层表值覆盖前面 fsel 的默认权重/路由参数。
                    cu.update(fnh=lsel(fp,Ly,isf,"fnh","afnh"), fnl=lsel(fp,Ly,isf,"fnl","afnl"),
                              hsc=lsel(fp,Ly,isf,"hsc","ahsc"), hbs=lsel(fp,Ly,isf,"hbs","ahbs"),
                              nw=lsel(fp,Ly,isf,"nw","anw"), gate=ltab(fp,Ly,"gate")(), gbias=ltab(fp,Ly,"gbias")()); // PY L404-L406
                    int tap0 = NL - 4;             // PY L409
                    cu.update(rk=sm + RKOFF, first=isf && Ly == FIRST_LY,
                              last=hf != 0 && (Ly == NL - 1 || (Ly >= tap0 && Ly <= tap0 + 2))); // PY L407-L410，保留原公式
                    if constexpr ((kind & 1) != 0) { // PY L412
                        cu.update(eng=hf != 0 && (ltab(fp,Ly,"lflags")() & 128) != 0,
                                  engkv=fptr(fp,"engkv"), enggw=ltab(fp,Ly,"enggw")(),
                                  engpart=fptr(fp,"engpart"), TR=TRx); // PY L413-L414
                    }
                    auto x8pub = [=](constexpr int k) { // PY L415，front 内部阶段的 callback
                        if constexpr (k == 5 && MS.sh_early(ceil_div(TRx, MS.MAXTOK))) { // PY L416
                            if (isf) {             // PY L417，仅 FFN front 发布
                                wait_storecnt0();  // PY L418
                                __syncthreads();   // PY L419
                                if (tq == 0) atomic_add(lc + LY.X8_PUB, 1); // PY L420-L421
                            }
                        }
                    };
                    FS.front_any(cu, x8pub);        // PY L422
                }

                if constexpr (MS.sh_early(ceil_div(TRx, MS.MAXTOK))) { // PY L423
                    if (hf == 0 && b >= FS.FRONT_CTAS &&
                        b < FS.FRONT_CTAS + ceil_div(TRx,MS.MAXTOK) * MS.NUG * MS.SHE_CTAS) { // PY L424-L426
                        int tq3 = thread_id();     // PY L427
                        if (tq3 == 0)              // PY L428
                            wait_count([=] { return lc + LY.X8_PUB; }, FS.FRONT_CTAS, site=6); // PY L429
                        __syncthreads();           // PY L430
                        auto ce = make_shared_context(fp, Ly, tq3, b, sm, TRx, RTOPK); // PY L431-L433
                        MS.ug_shared_early(ce, b - FS.FRONT_CTAS); // PY L434
                    }
                }
                if (hf == 0) {                     // PY L435
                    iprefetch(16);                 // PY L436
                    handoff(lc + LY.FRONT, t, true); // PY L437，所有 CTA 参与
                    auto cm = make_moe_context(fp, Ly, thread_id(), b, sm, TRx, RTOPK, lc); // PY L438-L443
                    MS.moe(cm, lc + LY.MOE_UG);     // PY L444
                    __syncthreads();               // PY L445
                    handoff(lc + LY.MOE_DONE, t, true); // PY L446
                    MS.moe_combine(Context(t=thread_id(), b=b, out=fptr(fp,"mout"), topk=RTOPK), TRx, sm); // PY L448
                    tp_allreduce(with_fields(c, tpout=fptr(fp,"tp2out"), ytgt=fptr(fp,"y2")),
                                 par * 2 + 1, 2 * Ly + 2); // PY L449
                    gpub(lc + LY.TP2_GROUPS, b, t); // PY L450
                }
            }
            handoff(lc + LY.LAYER_END, t, true);    // PY L451
            if constexpr ((kind & 1) != 0) {        // PY L452
                if (ltab(fp, Ly, "lflags")() & 16) { // PY L453
                    int tap0 = NL - 4;             // PY L454
                    CX.stage_tap1(Context(t=thread_id(), b=b, aux8=fptr(fp,"aux8"), auxs=fptr(fp,"auxs")),
                                  TRx, Ly - tap0, fptr(fp,"aRout")); // PY L455-L456
                }
            }
            stamp(18);                             // PY L457，没有新增 tap 后 handoff
        }
    }

    if constexpr (part == "target") {              // PY L458，在 segment 循环之外
        int t = thread_id(), b = logical_cta_id();  // PY L459-L460
        u64 sm = lds_base();                        // PY L461
        if (t == 0) gstore_u64(st + i64(b) * 256 + 25 * 8, clock64()); // PY L462-L463
        ST.target(tp, t, b, sm, st, cnt + i64(NL + NDR) * LCB, recv, rank,
                  head_d=4, ctx=context_table_or_null(fp, NDR), T=TR); // PY L464-L465
    }
    if constexpr (NDR > 0 && part != "target") {    // PY L466
        int t = thread_id(), b = logical_cta_id();  // PY L467-L468
        u64 sm = lds_base();                        // PY L469
        if (t == 0) gstore_u64(st + i64(b) * 256 + 26 * 8, clock64()); // PY L470-L471
        ST.draft(tp, t, b, sm, st, cnt + i64(NL + NDR) * LCB, recv, rank, head_d=4); // PY L472
    }
    tp_epoch_end(fp, tep);                          // PY L473
    hx.TOFLAG[0] = None;                            // PY L474，tracing 侧清理
    use_for_cache_key(keyed);                       // PY L475
}
