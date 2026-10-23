(() => {
  'use strict';
  const search = document.querySelector('#search');
  const category = document.querySelector('#category');
  const tbody = document.querySelector('#items');
  const empty = document.querySelector('#empty');
  const shownCount = document.querySelector('#shown-count');
  const inputCount = document.querySelector('#input-count');
  const categoryCount = document.querySelector('#category-count');
  const errorCount = document.querySelector('#error-count');
  const fileInput = document.querySelector('#html-import');
  const fileStatus = document.querySelector('#file-status');
  const csvLink = document.querySelector('.rf-download');
  const original = tbody.innerHTML;
  let blobUrl = null;
  let errors = 0;

  function currentRows() { return Array.from(tbody.querySelectorAll('tr')); }
  function cellText(tr, index) { return tr.cells[index]?.textContent?.trim() || ''; }
  function update() {
    const query = search.value.trim().toLocaleLowerCase('ja');
    const selected = category.value;
    let visible = 0;
    const rows = currentRows();
    for (const row of rows) {
      row.dataset.category = row.querySelector('.rf-category-edit')?.value || 'その他';
      const matches = (selected === 'all' || row.dataset.category === selected) && row.textContent.toLocaleLowerCase('ja').includes(query);
      row.hidden = !matches;
      if (matches) visible++;
    }
    empty.hidden = visible > 0;
    shownCount.textContent = `${visible} 件を表示中`;
    inputCount.textContent = String(rows.length);
    categoryCount.textContent = String(new Set(rows.map(r => r.dataset.category)).size);
    errorCount.textContent = String(errors);
  }
  function safeCsvCell(value) {
    let s = String(value || '');
    if (/^\s*[=+@\-\t\r]/.test(s)) s = "'" + s;
    return '"' + s.replace(/"/g, '""') + '"';
  }
  function makeCsv() {
    const cols = ['ページタイトル','カテゴリ','概要','参照URL','確認状況'];
    const lines = [cols.map(safeCsvCell).join(',')];
    for (const tr of currentRows()) {
      const status = tr.querySelector('.rf-status-edit')?.value || '要確認';
      if (status === '対象外') continue;
      const values = [(tr.querySelector('.rf-row-title')?.textContent?.trim() || cellText(tr,0)), tr.dataset.category, cellText(tr,2), tr.dataset.sourceUrl || '', status];
      lines.push(values.map(safeCsvCell).join(','));
    }
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    blobUrl = URL.createObjectURL(new Blob(['\uFEFF' + lines.join('\r\n')], {type:'text/csv;charset=utf-8'}));
    csvLink.href = blobUrl;
    csvLink.download = 'researchflow_results.csv';
  }
  function metadata(doc, selector, attribute='content') {
    return (doc.querySelector(selector)?.getAttribute(attribute) || '').trim();
  }
  function clean(s, max=200) { return String(s || '').replace(/\s+/g,' ').trim().slice(0,max); }
  function classify(text) {
    const title = clean(text.split('\n')[0] || text, 400).toLocaleLowerCase('ja');
    const candidates = [
      ['採用・求人',/採用|求人|募集要項|募集職種|インターン|recruit|careers/i],
      ['ニュース・記事',/プレスリリース|ニュース|お知らせ|記事|ブログ|コラム|news/i],
      ['イベント',/イベント|開催|フェス|祭り|マルシェ|ワークショップ|企画展|ライトアップ|セミナー/i],
      ['企業・団体',/会社概要|企業概要|会社案内|会社情報|企業情報|運営会社|団体概要|組織概要|company profile/i],
      ['商品・サービス',/サービス|製品|プロダクト|商品紹介|料金プラン|web制作|ホームページ制作|pricing/i],
      ['飲食・店舗',/レストラン|カフェ|喫茶|ベーカリー|パン屋|ランチ|スイーツ|ケーキ|食堂|飲食|焼き菓子/i],
      ['観光・施設',/観光|展望|史跡|神社|庭園|美術館|資料館|水族館|散策|見学|公園/i]
    ];
    const primary = title.split(/[|｜│]|\s[-–—]\s/)[0];
    const exact = candidates.filter(([,regex])=>regex.test(primary));
    if (exact.length === 1) return exact[0][0];
    return 'その他'; // Static preview is not the trained Python classifier.
  }
  function parseHtml(raw, fileName) {
    const doc = new DOMParser().parseFromString(raw,'text/html');
    const title = clean(metadata(doc,'meta[property="og:title"]') || doc.querySelector('title')?.textContent || doc.querySelector('h1')?.textContent || fileName);
    const description = clean(metadata(doc,'meta[name="description"]') || metadata(doc,'meta[property="og:description"]'),250);
    const canonical = clean(metadata(doc,'link[rel="canonical"]','href'),400);
    doc.querySelectorAll('script,style,nav,header,footer,aside,noscript').forEach(node=>node.remove());
    const body=clean(doc.querySelector('main')?.textContent || doc.querySelector('article')?.textContent || doc.body?.textContent,1500);
    const summary = clean(description || body,100);
    if(!title && !body)throw new Error('HTMLの本文が読み取れません');
    return {title, summary, category:classify(title+'\n'+description+'\n'+body), url:canonical, status:'要確認'};
  }
  function newCell(tr, text) { const td=document.createElement('td'); td.textContent=text; tr.appendChild(td); return td; }
  function optionSelect(className, options, value, label) {
    const select=document.createElement('select'); select.className=className; select.setAttribute('aria-label',label);
    for(const option of options){const el=document.createElement('option');el.textContent=option;el.value=option;if(option===value)el.selected=true;select.appendChild(el);}
    return select;
  }
  function render(items) {
    tbody.replaceChildren();
    for(const item of items){
      const tr=document.createElement('tr'); tr.dataset.category=item.category; tr.dataset.sourceUrl=item.url;
      const td=newCell(tr,item.title);td.className='rf-row-title';
      const cat=document.createElement('td');cat.appendChild(optionSelect('rf-category-edit',['企業・団体','商品・サービス','採用・求人','ニュース・記事','イベント','飲食・店舗','観光・施設','その他'],item.category,'カテゴリを編集'));tr.appendChild(cat);
      newCell(tr,item.summary);
      const status=document.createElement('td');status.appendChild(optionSelect('rf-status-edit',['要確認','確認済み','保留','対象外'],item.status,'確認状況を編集'));tr.appendChild(status);
      tbody.appendChild(tr);
    }
    update(); makeCsv();
  }
  fileInput.addEventListener('change', async () => {
    const files=Array.from(fileInput.files || []).slice(0,8);
    if(!files.length)return;
    const rows=[];errors=0;
    const seen=new Set();
    for(const file of files){
      try{
        if(file.size>1_000_000)throw new Error('容量超過');
        if(!/\.html?$/i.test(file.name))throw new Error('HTML以外の形式');
        const item=parseHtml(await file.text(),file.name);
        const key=item.title.toLocaleLowerCase('ja');
        if(seen.has(key))throw new Error('重複');
        seen.add(key); rows.push(item);
      }catch(error){errors++;}
    }
    render(rows);search.value='';category.value='all';update();
    fileStatus.textContent=`HTML ${files.length}件を解析／成功 ${rows.length}件／失敗・重複 ${errors}件（外部送信なし）`;
  });
  document.querySelector('#reset-demo').addEventListener('click', () => {
    tbody.innerHTML=original; fileInput.value=''; fileStatus.textContent='初期表示：架空のサンプル6件'; errors=0;
    search.value='';category.value='all';
    if(blobUrl){URL.revokeObjectURL(blobUrl);blobUrl=null;}
    update(); makeCsv();
  });
  tbody.addEventListener('change', event => {
    if(event.target.matches('.rf-category-edit,.rf-status-edit')) { update();makeCsv(); }
  });
  search.addEventListener('input',update);
  category.addEventListener('change',update);
  update(); makeCsv();
})();
