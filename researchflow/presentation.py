"""Shared, original page fragments for the HTML review page and Streamlit demo.

Design reference: the oversized typographic hierarchy and editorial page rhythm
of artvibes.co.jp. No third-party code, fonts or images are bundled.
"""

SITE_HEADER = """
<header class="rf-site-header" aria-label="Site navigation">
  <a class="rf-brand" href="#top" aria-label="ResearchFlow - to top">research<span>flow</span><i>.</i><small>WORK / 001</small></a>
  <nav class="rf-site-nav" aria-label="Sections">
    <a href="#case">ABOUT</a>
    <a href="#workflow">PROCESS</a>
    <a class="rf-nav-cta" href="#demo">DEMO <span aria-hidden="true">&#8599;</span></a>
  </nav>
</header>
"""

HERO = """
<section class="rf-hero" id="top" aria-labelledby="rf-hero-title">
  <div class="rf-hero-meta"><span>WEB MEDIA / RESEARCH TOOL</span><span>PERSONAL PROJECT / 2026</span></div>
  <div class="rf-hero-content">
    <p class="rf-hero-label"><span class="rf-square" aria-hidden="true"></span>RESEARCHFLOW / CASE STUDY 01</p>
    <h1 id="rf-hero-title">ページ情報を<br/><span class="rf-hero-emphasis">一覧表にまとめる</span></h1>
    <div class="rf-hero-lower">
      <div class="rf-hero-copy">
        <span class="rf-mini-index">WHAT IS RESEARCHFLOW?</span>
        <p class="rf-hero-lead">公開ページのURLや保存したHTMLから、タイトルと概要を抽出します。<br class="rf-only-desktop"/>自動分類した結果を確認・修正し、CSVで保存できます。</p>
        <span class="rf-hero-micro">実際の公開URLに対応 ／ 標準モードはAPIキー不要</span>
      </div>
      <a href="#demo" class="rf-action-primary" aria-label="See the research demo"><span>結果を<br>見る</span><b aria-hidden="true">&#8599;</b></a>
    </div>
  </div>
  <div class="rf-hero-bottom"><span>01 / 04</span><span>SCROLL &nbsp; &#8595;</span></div>
</section>
"""

FEATURE = """
<section class="rf-feature" id="case" aria-label="Project overview">
  <div class="rf-feature-top"><span>01 &mdash; OVERVIEW</span><span>FROM HTML TO CSV</span></div>
  <div class="rf-feature-main">
    <p class="rf-feature-statement">複数のページを<br/><em>一度に一覧化</em></p>
    <div class="rf-feature-bottom"><p class="rf-feature-desc">ページ情報を取得・分類し、一覧表で確認できます。必要な箇所を修正して、そのままCSVに保存できます。</p><a href="#workflow" class="rf-arrow-link" aria-label="How the process works">&#8599;</a></div>
  </div>
  <div class="rf-feature-spec"><span>OUTPUT</span><b>URL <i>&#8594;</i> CSV</b><span>PUBLIC PAGES &nbsp; / &nbsp; EDITABLE RESEARCH SHEET</span></div>
</section>
"""

WORKFLOW = """
<section class="rf-workflow-block" id="workflow" aria-label="Processing steps">
  <div class="rf-section-heading"><div><span class="rf-section-eyebrow">02 &mdash; PROCESS</span><h2>抽出からCSV出力まで</h2></div><p>公開URLやHTMLファイルを、抽出・分類・確認の順に処理します。</p></div>
  <div class="rf-workflow">
    <article class="rf-workflow-item">
       <span class="rf-step-no">01</span>
       <h3>抽出<small>EXTRACT</small></h3>
       <p>公開URLまたはHTMLファイルから、タイトル・概要・本文から情報を抽出します。</p>
       <span class="rf-step-arrow" aria-hidden="true">&#8599;</span>
    </article>
    <article class="rf-workflow-item">
       <span class="rf-step-no">02</span>
       <h3>分類<small>CLASSIFY</small></h3>
       <p>ページの用途を、明示語句とローカル分類モデルで整理します。曖昧な結果は確認できます。</p>
       <span class="rf-step-arrow" aria-hidden="true">&#8599;</span>
    </article>
    <article class="rf-workflow-item">
       <span class="rf-step-no">03</span>
       <h3>出力<small>EXPORT</small></h3>
       <p>分類や概要を編集し、確認したデータをCSVで保存できます。</p>
       <span class="rf-step-arrow" aria-hidden="true">&#8599;</span>
    </article>
  </div>
  <a class="rf-inline-link" href="#demo"><span>実際に試す</span><b aria-hidden="true">&#8599;</b></a>
</section>
"""

DEMO_INTRO = """
<div class="rf-demo-intro" id="demo">
  <div><span class="rf-section-eyebrow">03 &mdash; RESULT</span><h2 class="rf-results-title">情報収集を試す</h2></div>
  <div class="rf-demo-intro-side"><p>公開URLを最大8件まとめて取得できます。HTMLファイルの取り込みや、確認・修正した結果のCSV出力にも対応しています。</p><span>URL INPUT / HTML UPLOAD / CSV EXPORT</span></div>
</div>
"""

FOOTER = """
<footer class="rf-site-footer" aria-label="End of portfolio">
  <div class="rf-footer-top"><span>END OF CASE</span><a href="#top">BACK TO TOP &nbsp; &#8593;</a></div>
  <p class="rf-footer-heading">research<br><span>flow.</span></p>
  <div class="rf-footer-bottom"><span>WEB MEDIA &times; AUTOMATION / 2026</span><span>初期表示のサンプルデータは架空です。</span></div>
</footer>
"""

