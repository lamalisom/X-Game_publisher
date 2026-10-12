import re

def update_file(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_resolve_function = """function resolveLocation(lat: number, lng: number, countryRaw: string, cityName: string, spotName: string) {
  const name = (spotName || '').toLowerCase();
  const c = (countryRaw || '').trim().toUpperCase();
  const cityLower = (cityName || '').toLowerCase();

  // 1. 🇨🇭 瑞士 (CH) - 必須最優先判定（涵蓋 Laax, Zermatt, Verbier, Titlis, Jungfrau, Saas-Fee, St. Moritz, Davos 等）
  if (c === 'CH' || c === 'SWITZERLAND' || c === 'SUI' || c === '瑞士' || 
      name.includes('zermatt') || name.includes('laax') || name.includes('verbier') || name.includes('titlis') || 
      name.includes('jungfrau') || name.includes('saas-fee') || name.includes('moritz') || name.includes('davos') || 
      name.includes('zürich') || name.includes('geneva') || cityLower.includes('zermatt') || cityLower.includes('laax') || 
      (lat >= 45.8 && lat <= 47.9 && lng >= 5.9 && lng <= 10.5)) {
    let city = cityName || '阿爾卑斯 Alps';
    if (name.includes('zermatt') || cityLower.includes('zermatt')) city = '策馬特 Zermatt';
    else if (name.includes('laax') || cityLower.includes('laax')) city = '拉克斯 Laax';
    else if (name.includes('verbier') || cityLower.includes('verbier')) city = '韋爾比耶 Verbier';
    else if (name.includes('titlis')) city = '鐵力士山 Engelberg-Titlis';
    else if (name.includes('jungfrau') || name.includes('grindelwald')) city = '少女峰 Jungfrau';
    else if (name.includes('saas-fee')) city = '薩斯斐 Saas-Fee';
    else if (name.includes('moritz')) city = '聖莫里茨 St. Moritz';
    else if (name.includes('davos')) city = '達沃斯 Davos';
    else if (name.includes('zürich') || name.includes('zurich')) city = '蘇黎世 Zurich';
    else if (name.includes('geneva') || name.includes('genève')) city = '日內瓦 Geneva';
    return { flag: '🇨🇭', countryCode: 'CH', countryZH: '瑞士', countryEN: 'Switzerland', cityZH: city, cityEN: city };
  }

  // 2. 🇸🇪 瑞典 (SE) - 優先判定瑞典四大雪場與城市（Åre, Sälen, Riksgränsen, Hammarbybacken, Stockholm, Malmö, Gothenburg）
  if (c === 'SE' || c === 'SWEDEN' || c === 'SVERIGE' || c === '瑞典' || 
      name.includes('stockholm') || name.includes('hammarby') || name.includes('malmö') || name.includes('malmo') || 
      name.includes('gothenburg') || name.includes('göteborg') || name.includes('åre') || name.includes('sälen') || 
      name.includes('riksgränsen') || cityLower.includes('stockholm') || cityLower.includes('malmö') || cityLower.includes('gothenburg') || 
      (lat >= 55.3 && lat <= 69.1 && lng >= 11.0 && lng <= 24.2 && !(lat >= 58.0 && lat <= 64.0 && lng < 11.0))) {
    let city = cityName || '斯德哥爾摩 Stockholm';
    if (name.includes('malmö') || name.includes('malmo') || cityLower.includes('malmö') || cityLower.includes('malmo') || (lat >= 55.5 && lat <= 55.7 && lng >= 12.9 && lng <= 13.1)) city = '馬爾默 Malmö';
    else if (name.includes('gothenburg') || name.includes('göteborg') || cityLower.includes('gothenburg') || (lat >= 57.6 && lat <= 57.8 && lng >= 11.8 && lng <= 12.1)) city = '哥德堡 Gothenburg';
    else if (name.includes('åre') || name.includes('are')) city = '奧勒 Åre';
    else if (name.includes('sälen')) city = '塞倫 Sälen';
    else if (name.includes('riksgränsen')) city = '國家界 Riksgränsen';
    else if (name.includes('stockholm') || name.includes('hammarby') || cityLower.includes('stockholm') || (lat >= 59.2 && lat <= 59.4 && lng >= 17.9 && lng <= 18.2)) city = '斯德哥爾摩 Stockholm';
    return { flag: '🇸🇪', countryCode: 'SE', countryZH: '瑞典', countryEN: 'Sweden', cityZH: city, cityEN: city };
  }

  // 3. 🇫🇷 法國 (FR) - 包含 Chamonix, Avoriaz, Tignes, Val Thorens, Paris, Marseille
  if (c === 'FR' || c === 'FRANCE' || c === '法國' || 
      name.includes('paris') || name.includes('marseille') || name.includes('lyon') || name.includes('chamonix') || 
      name.includes('tignes') || name.includes('val thorens') || name.includes('avoriaz') || (lat >= 41.0 && lat <= 51.5 && lng >= -5.5 && lng <= 9.6)) {
    let city = cityName || '巴黎 Paris';
    if (name.includes('chamonix')) city = '霞慕尼 Chamonix';
    else if (name.includes('avoriaz') || name.includes('stash')) city = '阿沃里亞茲 Avoriaz';
    else if (name.includes('tignes')) city = '蒂涅 Tignes';
    else if (name.includes('val thorens') || name.includes('thorens')) city = '托倫斯谷 Val Thorens';
    else if (name.includes('marseille')) city = '馬賽 Marseille';
    else if (name.includes('lyon')) city = '里昂 Lyon';
    return { flag: '🇫🇷', countryCode: 'FR', countryZH: '法國', countryEN: 'France', cityZH: city, cityEN: city };
  }

  // 4. 🇳🇴 挪威 (NO)
  if (c === 'NO' || c === 'NORWAY' || c === 'NORGE' || c === '挪威' || 
      name.includes('oslo') || name.includes('bergen') || name.includes('trondheim') || name.includes('stavanger') || 
      name.includes('tromsø') || cityLower.includes('oslo') || cityLower.includes('bergen') || (lat >= 57.9 && lat <= 71.2 && lng >= 4.5 && lng <= 11.5)) {
    let city = cityName || '奧斯陸 Oslo';
    if (name.includes('bergen') || cityLower.includes('bergen')) city = '卑爾根 Bergen';
    else if (name.includes('trondheim') || cityLower.includes('trondheim')) city = '特隆赫姆 Trondheim';
    else if (name.includes('stavanger') || cityLower.includes('stavanger')) city = '斯塔萬格 Stavanger';
    else if (name.includes('tromsø') || name.includes('tromso')) city = '特羅姆瑟 Tromsø';
    else if (name.includes('oslo') || cityLower.includes('oslo')) city = '奧斯陸 Oslo';
    return { flag: '🇳🇴', countryCode: 'NO', countryZH: '挪威', countryEN: 'Norway', cityZH: city, cityEN: city };
  }"""

    # 替換整個 resolveLocation 函數的前半段
    pattern = r'function resolveLocation\s*\([^\)]*\)\s*\{[\s\S]*?(?=\/\/\s*🇬🇧|\/\/\s*🇯🇵|\/\/\s*🇰🇷|\/\/\s*🇭🇰|\/\/\s*🇹🇼|\/\/\s*🇺🇸|\/\/\s*🇨🇦|\/\/\s*🇹🇭|\/\/\s*🇮🇩|\/\/\s*🇫🇮)'
    content = re.sub(pattern, new_resolve_function + '\n\n  ', content, count=1)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'✅ Updated {fpath}')

update_file('src/pages/spots/map.astro')
update_file('src/pages/spots/map/en.astro')
