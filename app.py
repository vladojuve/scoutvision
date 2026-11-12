import io
import math
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title='ScoutVision | Football Analytics', page_icon='⚽', layout='wide')
st.title('⚽ ScoutVision · Football Analytics & Scouting')
st.caption('ScoutVision v5 · 2026/27 · Free multi-source football analytics · Android-friendly')

ROOT = 'https://raw.githubusercontent.com/oladeeayo/open-matchday/master'
SB = 'https://raw.githubusercontent.com/hudl/open-data/master/data'

# ----------------------------- DATA ACCESS -----------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_text(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

@st.cache_data(ttl=3600, show_spinner=False)
def get_csv(url):
    try:
        return pd.read_csv(io.StringIO(get_text(url)))
    except (requests.RequestException, pd.errors.EmptyDataError, ValueError):
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_json(url):
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def league_index():
    text = get_text(ROOT + '/LEAGUE_INDEX.md')
    rows = []
    for line in text.splitlines():
        if not line.startswith('| `'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 3:
            rows.append({'folder': cells[0].strip('`'), 'league': cells[1], 'country': cells[2]})
    return pd.DataFrame(rows)

@st.cache_data(ttl=3600)
def sb_competitions():
    return pd.DataFrame(get_json(SB + '/competitions.json'))

@st.cache_data(ttl=3600)
def sb_matches(competition_id, season_id):
    return pd.DataFrame(get_json(f'{SB}/matches/{competition_id}/{season_id}.json'))

@st.cache_data(ttl=3600)
def sb_events(match_id):
    return get_json(f'{SB}/events/{match_id}.json')

@st.cache_data(ttl=3600)
def sb_lineups(match_id):
    return get_json(f'{SB}/lineups/{match_id}.json')

@st.cache_data(ttl=3600)
def sb_360(match_id):
    return get_json(f'{SB}/three-sixty/{match_id}.json')

# ----------------------------- MATCHDAY HELPERS -----------------------------
def load_matches(folder, kind):
    return get_csv(f'{ROOT}/data/{folder}/{kind}_2627.csv')

def load_goals(folder):
    return get_csv(f'{ROOT}/data/{folder}/goals_2627.csv')

def played_table(df):
    teams = sorted(set(df['home'].dropna()) | set(df['away'].dropna()))
    rows = []
    for team in teams:
        home, away = df[df.home == team], df[df.away == team]
        w = int((home.ft_home > home.ft_away).sum() + (away.ft_away > away.ft_home).sum())
        d = int((home.ft_home == home.ft_away).sum() + (away.ft_away == away.ft_home).sum())
        l = len(home) + len(away) - w - d
        gf = int(home.ft_home.sum() + away.ft_away.sum())
        ga = int(home.ft_away.sum() + away.ft_home.sum())
        rows.append({'Tim': team, 'U': len(home)+len(away), 'P': w, 'N': d, 'I': l,
                     'DG': gf, 'PG': ga, 'GR': gf-ga, 'Bodovi': 3*w+d})
    return pd.DataFrame(rows).sort_values(['Bodovi','GR','DG'], ascending=False).reset_index(drop=True)

def team_games(df, team):
    x = df[(df.home == team) | (df.away == team)].copy()
    x['Postignuti'] = x.apply(lambda r: r.ft_home if r.home == team else r.ft_away, axis=1)
    x['Primljeni'] = x.apply(lambda r: r.ft_away if r.home == team else r.ft_home, axis=1)
    x['Ishod'] = x.apply(lambda r: 'P' if r.Postignuti > r.Primljeni else ('N' if r.Postignuti == r.Primljeni else 'I'), axis=1)
    return x.sort_values('date')

# ----------------------------- STATSBOMB EVENT PARSER -----------------------------
def nested_name(obj, key='name', default=''):
    return obj.get(key, default) if isinstance(obj, dict) else default

def xy(value):
    if isinstance(value, list) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            pass
    return None, None

def event_rows(raw_events):
    rows = []
    for e in raw_events:
        typ = nested_name(e.get('type', {}))
        locx, locy = xy(e.get('location'))
        pass_data = e.get('pass') or {}
        endx, endy = xy(pass_data.get('end_location'))
        if typ == 'Carry':
            endx, endy = xy((e.get('carry') or {}).get('end_location'))
        shot = e.get('shot') or {}
        duel = e.get('duel') or {}
        dribble = e.get('dribble') or {}
        interception = e.get('interception') or {}
        rows.append({
            'event_id': e.get('id'), 'index': e.get('index'), 'period': e.get('period'),
            'minute': e.get('minute'), 'second': e.get('second'), 'timestamp': e.get('timestamp'),
            'type': typ, 'team': nested_name(e.get('team', {}), default='Unknown'),
            'player': nested_name(e.get('player', {}), default='Unknown'),
            'position': nested_name(e.get('position', {})), 'possession': e.get('possession'),
            'x': locx, 'y': locy, 'end_x': endx, 'end_y': endy,
            'pass_recipient': nested_name(pass_data.get('recipient', {})),
            'pass_outcome': nested_name(pass_data.get('outcome', {})),
            'pass_length': pass_data.get('length'), 'pass_height': nested_name(pass_data.get('height', {})),
            'shot_xg': shot.get('statsbomb_xg'), 'shot_outcome': nested_name(shot.get('outcome', {})),
            'shot_body_part': nested_name(shot.get('body_part', {})),
            'duel_type': nested_name(duel.get('type', {})), 'duel_outcome': nested_name(duel.get('outcome', {})),
            'dribble_outcome': nested_name(dribble.get('outcome', {})),
            'interception_outcome': nested_name(interception.get('outcome', {})),
            'under_pressure': bool(e.get('under_pressure', False)),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        for c in ['minute','second','period','x','y','end_x','end_y','pass_length','shot_xg']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df['successful_pass'] = (df.type == 'Pass') & (df.pass_outcome == '')
        df['shot'] = df.type == 'Shot'
        df['goal'] = df.shot & (df.shot_outcome == 'Goal')
        df['carry_distance'] = ((df.end_x-df.x)**2 + (df.end_y-df.y)**2)**0.5
    return df

def pitch_figure(title='Pitch', height=560):
    fig = go.Figure()
    line = '#8b9aaa'
    fig.add_shape(type='rect', x0=0, y0=0, x1=120, y1=80, line=dict(color=line, width=1.5))
    fig.add_shape(type='line', x0=60, y0=0, x1=60, y1=80, line=dict(color=line, width=1))
    fig.add_shape(type='circle', x0=49, y0=29, x1=71, y1=51, line=dict(color=line, width=1))
    for x0, x1 in [(0,18),(102,120)]:
        fig.add_shape(type='rect', x0=x0, y0=18, x1=x1, y1=62, line=dict(color=line, width=1))
    for x0, x1 in [(0,6),(114,120)]:
        fig.add_shape(type='rect', x0=x0, y0=30, x1=x1, y1=50, line=dict(color=line, width=1))
    fig.update_layout(title=title, height=height, margin=dict(l=10,r=10,t=45,b=10),
                      plot_bgcolor='#176b46', paper_bgcolor='rgba(0,0,0,0)',
                      xaxis=dict(range=[-2,122],showgrid=False,zeroline=False,visible=False,scaleanchor='y',scaleratio=1.5),
                      yaxis=dict(range=[-2,82],showgrid=False,zeroline=False,visible=False),
                      font=dict(color='#e8eef5'))
    return fig

def make_summary(df):
    if df.empty:
        return pd.DataFrame()
    rows=[]
    for (team, player), g in df.groupby(['team','player']):
        shots=g[g.shot]
        passes=g[g.type=='Pass']
        carries=g[g.type=='Carry']
        defensive=g[g.type.isin(['Pressure','Ball Recovery','Interception','Duel','Block','Clearance','50/50'])]
        rows.append({'Team':team,'Player':player,'Events':len(g),'Minutes active':g.minute.max()-g.minute.min() if g.minute.notna().any() else None,
                     'Passes':len(passes),'Passes completed':int(passes.successful_pass.sum()),
                     'Pass completion %':round(100*passes.successful_pass.mean(),1) if len(passes) else None,
                     'Shots':len(shots),'Goals':int(shots.shot_outcome.eq('Goal').sum()),
                     'xG':round(shots.shot_xg.sum(),3) if shots.shot_xg.notna().any() else 0,
                     'Carries':len(carries),'Carry distance (event units)':round(carries.carry_distance.sum(),1) if len(carries) else 0,
                     'Pressures':int(g.type.eq('Pressure').sum()),'Defensive events':len(defensive),
                     'Duels':int(g.type.eq('Duel').sum()),'Interceptions':int(g.type.eq('Interception').sum()),
                     'Recoveries':int(g.type.eq('Ball Recovery').sum())})
    return pd.DataFrame(rows)

# ----------------------------- APP NAVIGATION -----------------------------
section = st.sidebar.radio('Modul', ['🌐 Pregled svih liga 2026/27', '🌍 Aktuelne lige 2026/27', '🆕 Free Player Data Lab', '🔬 StatsBomb Event Lab', '🧠 Player Scout & Compare'])

if section == '🌐 Pregled svih liga 2026/27':
    st.header('Pregled svih dostupnih liga · 2026/27')
    st.caption('Izvor: Open Matchday. Ovaj pregled koristi javne CSV datoteke; osvežavanje izvora je dnevno, a pokrivenost statistike zavisi od lige.')
    try:
        leagues = league_index()
        if leagues.empty:
            st.error('Indeks liga nije dostupan.')
            st.stop()
        countries = sorted(leagues.country.dropna().unique())
        country_filter = st.selectbox('Država / region', ['Sve'] + countries, index=0)
        visible = leagues if country_filter == 'Sve' else leagues[leagues.country == country_filter]
        search = st.text_input('Pretraži ligu ili državu', placeholder='Npr. Serie A, Austria, Serbia...').strip().lower()
        if search:
            visible = visible[visible.apply(lambda r: search in str(r['league']).lower() or search in str(r['country']).lower() or search in str(r['folder']).lower(), axis=1)]
        st.metric('Takmičenja u izboru', len(visible))
        st.dataframe(visible[['country','league','folder']].rename(columns={'country':'Država / region','league':'Takmičenje','folder':'ID izvora'}), use_container_width=True, hide_index=True)
        st.divider()
        st.subheader('Detalji izabranog takmičenja')
        if not visible.empty:
            opts = visible.reset_index(drop=True)
            idx = st.selectbox('Takmičenje', opts.index.tolist(), format_func=lambda i: f"{opts.loc[i,'country']} · {opts.loc[i,'league']}")
            selected_league = opts.loc[idx]
            with st.spinner('Učitavam rezultate, raspored i golove...'):
                results = load_matches(selected_league['folder'], 'results')
                fixtures = load_matches(selected_league['folder'], 'fixtures')
                goals = load_goals(selected_league['folder'])
            for col in ['ft_home','ft_away']:
                if col in results: results[col] = pd.to_numeric(results[col], errors='coerce')
            results = results.dropna(subset=['home','away','ft_home','ft_away']) if not results.empty else results
            c1,c2,c3,c4 = st.columns(4)
            c1.metric('Odigrane utakmice', len(results))
            c2.metric('Raspored', len(fixtures))
            c3.metric('Zabeleženi golovi', len(goals))
            c4.metric('Timovi', len(set(results.home)|set(results.away)) if not results.empty else 0)
            if not results.empty:
                st.subheader('Tabela iz dostupnih rezultata')
                st.dataframe(played_table(results), use_container_width=True, hide_index=True)
                show = results.sort_values('date', ascending=False)
                cols = [c for c in ['date','gw','home','ft_home','ft_away','away','home_shots','away_shots','home_target','away_target','home_corners','away_corners','home_yellow','away_yellow','home_red','away_red'] if c in show.columns]
                st.subheader('Rezultati i dostupna statistika utakmica')
                st.dataframe(show[cols], use_container_width=True, hide_index=True)
            if not fixtures.empty:
                st.subheader('Predstojeće utakmice')
                st.dataframe(fixtures.sort_values('date'), use_container_width=True, hide_index=True)
            if not goals.empty:
                st.subheader('Golovi i strelci')
                st.dataframe(goals.sort_values(['date','minute'], ascending=[False, True]), use_container_width=True, hide_index=True)
            else:
                st.info('Za ovo takmičenje izvor trenutno ne objavljuje posebnu datoteku sa strelcima i minutima golova.')
            if not results.empty:
                stat_cols = [c for c in ['home_shots','away_shots','home_target','away_target','home_fouls','away_fouls','home_corners','away_corners','home_yellow','away_yellow','home_red','away_red'] if c in results.columns]
                if stat_cols:
                    availability = pd.DataFrame({'Polje':stat_cols, 'Popunjeno':[(results[c].notna().sum()) for c in stat_cols], 'Ukupno utakmica':[len(results)]*len(stat_cols)})
                    availability['Pokrivenost %'] = (100*availability['Popunjeno']/availability['Ukupno utakmica'].replace(0,1)).round(1)
                    st.subheader('Kontrola pokrivenosti statistike')
                    st.dataframe(availability, use_container_width=True, hide_index=True)
                    st.caption('Prazno polje znači da izvor nema podatak; ne znači nulu.')
        else:
            st.info('Nema takmičenja za ovaj filter.')
    except Exception as e:
        st.error('Ne mogu da učitam pregled liga. Pokušaj ponovo kasnije.')
        st.caption(str(e))

if section == '🌍 Aktuelne lige 2026/27':
    st.header('Aktuelne lige · 2026/27')
    try:
        leagues = league_index()
        countries = sorted(leagues.country.dropna().unique())
        default_country = countries.index('Austria') if 'Austria' in countries else 0
        country = st.sidebar.selectbox('Država', countries, index=default_country)
        available = leagues[leagues.country == country]
        chosen = st.sidebar.selectbox('Liga', available.league.tolist())
        folder = available.loc[available.league == chosen, 'folder'].iloc[0]
        st.subheader(f'{country} · {chosen} · 2026/27')
        with st.spinner('Učitavam podatke...'):
            results, fixtures = load_matches(folder, 'results'), load_matches(folder, 'fixtures')
        if results.empty and fixtures.empty:
            st.warning('Za ovu ligu trenutno nema dostupnih redova. Probaj drugu ligu.')
            st.stop()
        if not results.empty:
            for col in ['ft_home','ft_away']:
                results[col] = pd.to_numeric(results[col], errors='coerce')
            results = results.dropna(subset=['home','away','ft_home','ft_away']).sort_values('date', ascending=False)
        a,b,c=st.columns(3)
        a.metric('Odigrane utakmice',len(results)); b.metric('Zakazane utakmice',len(fixtures))
        c.metric('Timovi',len(set(results.home)|set(results.away)) if not results.empty else len(set(fixtures.home)|set(fixtures.away)))
        tabs=st.tabs(['🏆 Tabela','📅 Rezultati i raspored','📈 Analiza tima','⚔️ Poređenje timova','🎯 Statistika meča'])
        with tabs[0]:
            if not results.empty:
                st.caption('Tabela je izračunata iz dostupnih rezultata; kod kupova i plej-ofa ne mora predstavljati zvanični plasman.')
                st.dataframe(played_table(results),use_container_width=True,hide_index=True)
            else: st.info('Još nema odigranih utakmica.')
        with tabs[1]:
            if not results.empty:
                show=results[['date','gw','home','ft_home','ft_away','away']].copy(); show.columns=['Datum','Kolo','Domaćin','Golovi D','Golovi G','Gost']
                st.dataframe(show,use_container_width=True,hide_index=True)
            if not fixtures.empty:
                cols=[x for x in ['date','time','gw','home','away'] if x in fixtures.columns]
                st.dataframe(fixtures[cols].sort_values('date'),use_container_width=True,hide_index=True)
        with tabs[2]:
            if results.empty: st.info('Nema rezultata za analizu.')
            else:
                team=st.selectbox('Izaberi klub',sorted(set(results.home)|set(results.away)))
                tg=team_games(results,team); x,y,z=st.columns(3)
                x.metric('Utakmice',len(tg)); y.metric('Golovi po utakmici',f'{tg.Postignuti.mean():.2f}'); z.metric('Primljeni po utakmici',f'{tg.Primljeni.mean():.2f}')
                st.markdown('**Forma – poslednjih 5:** '+' · '.join(tg.tail(5).Ishod.tolist()))
                chart=tg[['date','Postignuti','Primljeni']].melt('date',var_name='Tip',value_name='Golovi')
                st.plotly_chart(px.line(chart,x='date',y='Golovi',color='Tip',markers=True,title='Golovi po utakmici'),use_container_width=True)
                st.dataframe(tg[['date','home','ft_home','ft_away','away','Ishod']].sort_values('date',ascending=False),use_container_width=True,hide_index=True)
        with tabs[3]:
            if results.empty or len(set(results.home)|set(results.away))<2: st.info('Potrebne su bar dve ekipe sa odigranim utakmicama.')
            else:
                teams=sorted(set(results.home)|set(results.away)); t1,t2=st.columns(2)
                first=t1.selectbox('Prvi tim',teams,index=0); second=t2.selectbox('Drugi tim',teams,index=1)
                comp=[]
                for team in [first,second]:
                    g=team_games(results,team); wins=int((g.Ishod=='P').sum()); draws=int((g.Ishod=='N').sum())
                    comp.append({'Tim':team,'Utakmice':len(g),'Pobede':wins,'Bodovi':wins*3+draws,'Golovi / meč':round(g.Postignuti.mean(),2),'Primljeni / meč':round(g.Primljeni.mean(),2)})
                st.dataframe(pd.DataFrame(comp),use_container_width=True,hide_index=True)
                st.plotly_chart(px.bar(pd.DataFrame(comp),x='Tim',y=['Golovi / meč','Primljeni / meč'],barmode='group'),use_container_width=True)
        with tabs[4]:
            if results.empty: st.info('Nema utakmica.')
            else:
                opts=results.reset_index(drop=True)
                ix=st.selectbox('Utakmica',list(range(len(opts))),format_func=lambda i:f"{opts.iloc[i]['date']} · {opts.iloc[i]['home']} {int(opts.iloc[i]['ft_home'])}:{int(opts.iloc[i]['ft_away'])} {opts.iloc[i]['away']}")
                m=opts.iloc[ix]; st.markdown(f"### {m['home']} {int(m['ft_home'])} : {int(m['ft_away'])} {m['away']}")
                labels=[('Šutevi','home_shots','away_shots'),('U okvir','home_target','away_target'),('Korneri','home_corners','away_corners'),('Faulovi','home_fouls','away_fouls'),('Žuti kartoni','home_yellow','away_yellow'),('Crveni kartoni','home_red','away_red')]
                stats=[]
                for name,h,a in labels:
                    hv=pd.to_numeric(m.get(h),errors='coerce'); av=pd.to_numeric(m.get(a),errors='coerce')
                    if pd.notna(hv) and pd.notna(av): stats.append({'Statistika':name,str(m['home']):int(hv),str(m['away']):int(av)})
                if stats: st.dataframe(pd.DataFrame(stats),use_container_width=True,hide_index=True)
                else: st.info('Detaljna statistika nije dostupna; prazna polja nisu nule.')
        st.caption('Izvor: open-matchday (GitHub). Podaci zavise od pokrivenosti i ažuriranja izvora.')
    except Exception as e:
        st.error('Ne mogu da učitam modul aktuelnih liga. Proveri vezu ili pokušaj kasnije.')
        st.exception(e)


elif section == '🆕 Free Player Data Lab':
    st.header('Free Player Data Lab · 2026/27')
    st.markdown(
        'Dodatni besplatni izvor aktuelnih podataka o igračima: **API-Football Free**. '
        'Potrebni su besplatan nalog i API ključ; nije potrebna pretplata. '
        'Učitavamo samo izabrano takmičenje i stranicu igrača da čuvamo dnevnu kvotu.'
    )
    st.warning(
        'API ključ unesi samo u ovo polje. Nemoj ga slati u chat, stavljati u GitHub kod '
        'ili deliti screenshot na kojem se vidi.'
    )
    api_key = st.text_input('API-Football ključ (x-apisports-key)', type='password', key='apif_key')
    season = st.selectbox('Sezona (API oznaka)', [2026, 2025, 2024], index=0, key='apif_season')
    API_BASE = 'https://v3.football.api-sports.io'

    @st.cache_data(ttl=86400, show_spinner=False)
    def apif_get(endpoint, params_tuple, key):
        response = requests.get(
            API_BASE + endpoint,
            headers={'x-apisports-key': key},
            params=dict(params_tuple),
            timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('errors'):
            raise ValueError(str(payload['errors']))
        return payload

    if not api_key:
        st.info('Napravi besplatan API-Football nalog i preuzmi API ključ. Zatim ga unesi ovde.')
        st.markdown('[API-Football registracija](https://www.api-football.com/) · [Cene i kvote](https://www.api-football.com/pricing)')
        st.caption('Besplatna kvota je ograničena; proveri aktuelno stanje na svom API dashboard-u.')
    else:
        try:
            with st.spinner('Učitavam takmičenja za izabranu sezonu...'):
                league_payload = apif_get('/leagues', (('season', int(season)),), api_key)
            league_rows = []
            for item in league_payload.get('response', []):
                league = item.get('league') or {}
                country = item.get('country') or {}
                seasons = item.get('seasons') or []
                season_row = next((s for s in seasons if int(s.get('year', -1)) == int(season)), None)
                if season_row:
                    coverage = season_row.get('coverage') or {}
                    player_coverage = coverage.get('players') or {}
                    league_rows.append({
                        'league_id': league.get('id'),
                        'Takmičenje': league.get('name'),
                        'Država': country.get('name'),
                        'Tip': league.get('type'),
                        'Statistika igrača': bool(player_coverage.get('statistics')),
                        'Sezona': season,
                    })
            league_df = pd.DataFrame(league_rows)
            if league_df.empty:
                st.warning('API nije vratio takmičenja za ovu sezonu. Proveri sezonu ili API kvotu.')
            else:
                st.metric('Takmičenja vraćena za sezonu', len(league_df))
                country_options = ['Sve'] + sorted(league_df.Država.dropna().unique().tolist())
                chosen_country = st.selectbox('Država', country_options, key='apif_country')
                league_view = league_df if chosen_country == 'Sve' else league_df[league_df.Država == chosen_country]
                st.dataframe(league_view.drop(columns=['league_id']), use_container_width=True, hide_index=True)
                available = league_view[league_view['Statistika igrača'] == True]
                if available.empty:
                    st.info('Za ovaj izbor API ne označava dostupnu statistiku igrača.')
                else:
                    labels = available.apply(lambda r: f"{r['Država']} · {r['Takmičenje']} (ID {int(r['league_id'])})", axis=1).tolist()
                    selected_label = st.selectbox('Takmičenje za bazu igrača', labels, key='apif_league')
                    chosen_row = available.iloc[labels.index(selected_label)]
                    league_id = int(chosen_row.league_id)
                    page = st.number_input('Stranica igrača', min_value=1, max_value=50, value=1, step=1, key='apif_page')
                    if st.button('Učitaj igrače i statistiku', type='primary', key='apif_load'):
                        with st.spinner('Učitavam jednu stranicu igrača...'):
                            players_payload = apif_get(
                                '/players',
                                (('league', league_id), ('season', int(season)), ('page', int(page))),
                                api_key
                            )
                        player_rows = []
                        for item in players_payload.get('response', []):
                            player = item.get('player') or {}
                            stats_list = item.get('statistics') or []
                            stat = stats_list[0] if stats_list else {}
                            games = stat.get('games') or {}
                            goals = stat.get('goals') or {}
                            shots = stat.get('shots') or {}
                            passes = stat.get('passes') or {}
                            tackles = stat.get('tackles') or {}
                            duels = stat.get('duels') or {}
                            dribbles = stat.get('dribbles') or {}
                            fouls = stat.get('fouls') or {}
                            cards = stat.get('cards') or {}
                            player_rows.append({
                                'Player ID': player.get('id'), 'Igrač': player.get('name'),
                                'Država': player.get('nationality'), 'Godine': player.get('age'),
                                'Klub': (stat.get('team') or {}).get('name'),
                                'Pozicija': games.get('position'), 'Nastupi': games.get('appearences'),
                                'Startovi': games.get('lineups'), 'Minuti': games.get('minutes'),
                                'Golovi': goals.get('total'), 'Asistencije': goals.get('assists'),
                                'Šutevi': shots.get('total'), 'U okvir': shots.get('on'),
                                'Dodavanja': passes.get('total'), 'Ključna dodavanja': passes.get('key'),
                                'Preciznost dodavanja %': passes.get('accuracy'),
                                'Tackles': tackles.get('total'), 'Interceptions': tackles.get('interceptions'),
                                'Blocks': tackles.get('blocks'), 'Duels': duels.get('total'),
                                'Duels won': duels.get('won'), 'Dribbles': dribbles.get('attempts'),
                                'Dribbles successful': dribbles.get('success'),
                                'Fouls committed': fouls.get('committed'),
                                'Yellow': cards.get('yellow'), 'Red': cards.get('red')
                            })
                        players_df = pd.DataFrame(player_rows)
                        if players_df.empty:
                            st.warning('Nema igrača na ovoj stranici ili statistika nije dostupna.')
                        else:
                            st.session_state['apif_players_df'] = players_df
                            st.success(f"Učitano {len(players_df)} igrača · {selected_label}")
                    if 'apif_players_df' in st.session_state:
                        players_df = st.session_state['apif_players_df']
                        st.dataframe(players_df, use_container_width=True, hide_index=True)
                        player_names = players_df['Igrač'].fillna('Unknown').tolist()
                        selected_names = st.multiselect('Izaberi do 10 igrača za poređenje', player_names, max_selections=10, key='apif_compare')
                        metric_options = [c for c in ['Golovi','Asistencije','Minuti','Nastupi','Šutevi','U okvir','Dodavanja','Ključna dodavanja','Tackles','Interceptions','Blocks','Duels','Duels won','Dribbles successful'] if c in players_df.columns]
                        metric = st.selectbox('Metrika za poređenje', metric_options, key='apif_metric')
                        comparison = players_df[players_df['Igrač'].isin(selected_names)].copy()
                        if not comparison.empty:
                            comparison['Vrednost'] = pd.to_numeric(comparison[metric], errors='coerce')
                            st.plotly_chart(px.bar(comparison, x='Igrač', y='Vrednost', color='Klub', title=f'{metric} · izabrano takmičenje'), use_container_width=True)
                        numeric = players_df.copy()
                        for col in metric_options:
                            numeric[col] = pd.to_numeric(numeric[col], errors='coerce')
                        if 'Minuti' in numeric.columns:
                            for col in metric_options:
                                numeric[col + ' / 90'] = numeric[col] * 90 / numeric['Minuti'].replace(0, pd.NA)
                            per90_options = [c for c in numeric.columns if c.endswith(' / 90')]
                            per90_metric = st.selectbox('Per-90 metrika', per90_options, key='apif_per90')
                            st.dataframe(numeric[['Igrač','Klub','Pozicija','Minuti',per90_metric]].sort_values(per90_metric, ascending=False), use_container_width=True, hide_index=True)
                            st.caption('Per 90 se računa samo iz minuta koje je vratio API. Ovo nije percentile.')
                        st.download_button('Preuzmi igrače (CSV)', players_df.to_csv(index=False).encode('utf-8'), file_name='scoutvision_free_player_data.csv', mime='text/csv')
        except requests.HTTPError as e:
            st.error(f'API-Football HTTP greška: {e}. Proveri ključ, kvotu i pristup.')
        except requests.RequestException as e:
            st.error(f'Ne mogu da kontaktiram API-Football: {e}')
        except Exception as e:
            st.error('Greška pri učitavanju API-Football podataka.')
            st.caption(str(e))

elif section == '🔬 StatsBomb Event Lab':
    st.header('StatsBomb Event Lab')
    st.info('Open Data pokriva izabrana takmičenja i sezone, ne sve aktuelne lige. Dostupnost 360 podataka zavisi od utakmice.')
    try:
        comps=sb_competitions()
        comps['label']=comps['country_name'].astype(str)+' · '+comps['competition_name'].astype(str)+' · '+comps['season_name'].astype(str)
        selected=st.selectbox('Takmičenje i sezona',comps.index.tolist(),format_func=lambda i:comps.loc[i,'label'])
        cid,sid=int(comps.loc[selected,'competition_id']),int(comps.loc[selected,'season_id'])
        matches=sb_matches(cid,sid)
        if matches.empty:
            st.warning('Nema utakmica za ovaj izbor.')
        else:
            match_names=matches.apply(lambda r:f"{r['match_date']} · {r['home_team']['home_team_name']} {r['home_score']}:{r['away_score']} {r['away_team']['away_team_name']}",axis=1)
            ix=st.selectbox('Utakmica',matches.index.tolist(),format_func=lambda i:match_names.loc[i])
            match=matches.loc[ix]; match_id=int(match.match_id)
            st.caption(f"Match ID: {match_id} · {match['competition']['competition_name']} · {match['season']['season_name']}")
            with st.spinner('Učitavam događaje i sastave...'):
                raw=sb_events(match_id)
                events=event_rows(raw)
            if events.empty:
                st.warning('Nema event podataka za ovu utakmicu.')
                st.stop()
            teams=sorted(events.team.dropna().unique())
            team=st.selectbox('Tim',teams)
            team_events=events[events.team==team].copy()
            players=sorted(team_events.player.dropna().unique())
            player_choice=st.selectbox('Igrač', ['Svi igrači']+players)
            view=team_events if player_choice=='Svi igrači' else team_events[team_events.player==player_choice]

            shots=team_events[team_events.shot]
            passes=team_events[team_events.type=='Pass']
            completed=passes[passes.successful_pass]
            defensive=team_events[team_events.type.isin(['Pressure','Ball Recovery','Interception','Duel','Block','Clearance','50/50','Foul Won'])]
            c1,c2,c3,c4,c5=st.columns(5)
            c1.metric('Događaji',len(team_events)); c2.metric('Dodavanja',len(passes)); c3.metric('Uspešna dodavanja',len(completed))
            c4.metric('Šutevi',len(shots)); c5.metric('xG',f"{shots.shot_xg.sum():.2f}")

            tabs=st.tabs(['📊 Player Stats','🟢 Shot Map','➡️ Pass Map','🛡️ Defensive Map','🔥 Touch / Event Heatmap','📋 Event Explorer','👥 Lineups'])
            with tabs[0]:
                summary=make_summary(team_events)
                if player_choice!='Svi igrači': summary=summary[summary.Player==player_choice]
                st.dataframe(summary.sort_values('xG',ascending=False),use_container_width=True,hide_index=True)
                if not summary.empty:
                    metric=st.selectbox('Metrika za rangiranje', ['xG','Shots','Passes completed','Pass completion %','Carries','Pressures','Defensive events','Interceptions','Recoveries'])
                    st.plotly_chart(px.bar(summary.sort_values(metric,ascending=False).head(20),x='Player',y=metric,color='Team',title=f'{metric} · {team}'),use_container_width=True)
                st.caption('Ovo su zbirne vrednosti iz događaja za izabranu utakmicu, ne sezonski per-90 pokazatelji.')
            with tabs[1]:
                if shots.empty: st.info('Nema šuteva za izabrani tim.')
                else:
                    fig=pitch_figure('Shot map')
                    fig.add_trace(go.Scatter(x=shots.x,y=shots.y,mode='markers',marker=dict(size=10,color=shots.shot_xg,colorscale='YlOrRd',showscale=True,colorbar=dict(title='xG'),line=dict(color='white',width=0.6)),text=shots.apply(lambda r:f"{r.player}<br>xG: {r.shot_xg:.3f}<br>{r.shot_outcome}",axis=1),hovertemplate='%{text}<extra></extra>'))
                    st.plotly_chart(fig,use_container_width=True)
                    st.dataframe(shots[['minute','player','shot_xg','shot_outcome','shot_body_part']],use_container_width=True,hide_index=True)
            with tabs[2]:
                if completed.empty: st.info('Nema uspešnih dodavanja sa koordinatama.')
                else:
                    fig=pitch_figure('Completed pass map')
                    sample=completed.dropna(subset=['x','y','end_x','end_y'])
                    for _,r in sample.iterrows():
                        fig.add_trace(go.Scatter(x=[r.x,r.end_x],y=[r.y,r.end_y],mode='lines',line=dict(color='#d6f4e2',width=1.2),opacity=0.55,hoverinfo='skip',showlegend=False))
                    fig.add_trace(go.Scatter(x=sample.x,y=sample.y,mode='markers',marker=dict(size=4,color='#ffffff'),text=sample.apply(lambda r:f"{r.player} → {r.pass_recipient or 'nepoznat primalac'}",axis=1),hovertemplate='%{text}<extra></extra>',showlegend=False))
                    st.plotly_chart(fig,use_container_width=True)
                    st.caption('Linije prikazuju početnu i završnu lokaciju uspešnih dodavanja. Koordinate su StatsBomb 120×80.')
            with tabs[3]:
                if defensive.empty: st.info('Nema evidentiranih odbrambenih događaja za tim.')
                else:
                    fig=pitch_figure('Defensive actions & pressures')
                    fig.add_trace(go.Scatter(x=defensive.x,y=defensive.y,mode='markers',marker=dict(size=8,color=defensive.type.astype('category').cat.codes,colorscale='Turbo',showscale=True,colorbar=dict(title='Event type')),text=defensive.apply(lambda r:f"{r.player}<br>{r.type}<br>Min {r.minute}",axis=1),hovertemplate='%{text}<extra></extra>'))
                    st.plotly_chart(fig,use_container_width=True)
                    st.dataframe(defensive[['minute','player','type','duel_type','duel_outcome','interception_outcome']],use_container_width=True,hide_index=True)
            with tabs[4]:
                touches=view.dropna(subset=['x','y'])
                if touches.empty: st.info('Nema lokacija za izabrani filter.')
                else:
                    fig=pitch_figure('Event location density')
                    fig.add_trace(go.Histogram2dContour(x=touches.x,y=touches.y,colorscale='YlGnBu',ncontours=12,showscale=True,colorbar=dict(title='Events'),contours=dict(showlines=False),opacity=0.8))
                    st.plotly_chart(fig,use_container_width=True)
                    st.caption('Prikaz lokacija događaja u ovom meču. To nije tracking heatmap niti posed po sekundama.')
            with tabs[5]:
                event_types=['All']+sorted(team_events.type.dropna().unique().tolist())
                chosen_type=st.selectbox('Vrsta događaja',event_types)
                filtered=view if chosen_type=='All' else view[view.type==chosen_type]
                cols=['minute','second','team','player','position','type','x','y','end_x','end_y','pass_recipient','pass_outcome','shot_xg','shot_outcome','under_pressure']
                st.dataframe(filtered[[c for c in cols if c in filtered.columns]].sort_values(['period','minute','second']),use_container_width=True,hide_index=True)
                st.download_button('Preuzmi filtrirane događaje (CSV)',filtered.to_csv(index=False).encode('utf-8'),file_name=f'statsbomb_{match_id}_events.csv',mime='text/csv')
            with tabs[6]:
                try:
                    lineups=sb_lineups(match_id)
                    lineup_rows=[]
                    for item in lineups:
                        tname=item.get('team_name','')
                        for p in item.get('lineup',[]):
                            lineup_rows.append({'Team':tname,'Player':nested_name(p.get('player',{})),'Position':nested_name(p.get('position',{})),'Jersey':p.get('jersey_number')})
                    if lineup_rows: st.dataframe(pd.DataFrame(lineup_rows),use_container_width=True,hide_index=True)
                    else: st.info('Sastavi nisu dostupni u ovom fajlu.')
                except Exception: st.info('Sastavi nisu dostupni za ovu utakmicu.')
            st.caption('Izvor: Hudl / StatsBomb Open Data. Događaji su match-level; za sezonu, 360 i napredne agregate potrebni su dodatni podaci. Nije dozvoljeno predstavljati nepostojeće podatke kao nule.')
    except requests.RequestException:
        st.error('StatsBomb podaci trenutno nisu dostupni. Pokušaj ponovo kasnije.')
    except Exception as e:
        st.error('Greška pri obradi izabranih StatsBomb podataka.')
        st.caption(str(e))


elif section == '🧠 Player Scout & Compare':
    st.header('Player Scout & Compare · StatsBomb')
    st.write('Agregacija događaja iz više utakmica izabranog takmičenja. Rezultati važe samo za odabrani uzorak utakmica; nisu automatski kompletna sezonska statistika.')
    try:
        comps = sb_competitions()
        comps['label'] = comps['country_name'].astype(str) + ' · ' + comps['competition_name'].astype(str) + ' · ' + comps['season_name'].astype(str)
        selected = st.selectbox('Takmičenje i sezona', comps.index.tolist(), format_func=lambda i: comps.loc[i, 'label'], key='sc_comp')
        cid, sid = int(comps.loc[selected, 'competition_id']), int(comps.loc[selected, 'season_id'])
        matches = sb_matches(cid, sid)
        if matches.empty:
            st.warning('Za ovaj izbor nema utakmica.')
        else:
            matches = matches.copy()
            matches['label'] = matches.apply(lambda r: f"{r['match_date']} · {r['home_team']['home_team_name']} {r['home_score']}:{r['away_score']} {r['away_team']['away_team_name']}", axis=1)
            # Default to most recent 5 available matches; user can choose a larger sample.
            default_ids = matches.tail(min(5, len(matches))).index.tolist()
            chosen_ids = st.multiselect('Izaberi utakmice za analizu (preporuka: 3–10 za početak)', matches.index.tolist(), default=default_ids,
                                        format_func=lambda i: matches.loc[i, 'label'], key='sc_matches')
            if not chosen_ids:
                st.info('Izaberi najmanje jednu utakmicu.')
            else:
                if len(chosen_ids) > 20:
                    st.warning('Izabrano je više od 20 utakmica. Učitavanje može potrajati; za prvi test preporučujem najviše 10.')
                chunks=[]
                errors=[]
                progress=st.progress(0, text='Priprema utakmica...')
                for n, idx in enumerate(chosen_ids):
                    row=matches.loc[idx]
                    try:
                        raw=sb_events(int(row.match_id))
                        ev=event_rows(raw)
                        if not ev.empty:
                            ev['match_id']=int(row.match_id)
                            ev['match_date']=str(row.match_date)
                            ev['match_label']=row['label']
                            chunks.append(ev)
                    except Exception as ex:
                        errors.append(f"{row['label']}: {str(ex)[:140]}")
                    progress.progress((n+1)/len(chosen_ids), text=f'Učitano {n+1}/{len(chosen_ids)} utakmica')
                progress.empty()
                if errors:
                    with st.expander(f'Neuspešno učitavanje: {len(errors)} utakmica'):
                        for err in errors: st.write('• '+err)
                if not chunks:
                    st.error('Nema dostupnih događaja u izabranom uzorku.')
                else:
                    data=pd.concat(chunks, ignore_index=True)
                    data=data[data.player.notna() & (data.player!='Unknown')].copy()
                    appearances=data.groupby('player').match_id.nunique().rename('Matches in sample')
                    rows=[]
                    for player, g in data.groupby('player'):
                        shots=g[g.shot]
                        passes=g[g.type=='Pass']
                        carries=g[g.type=='Carry']
                        duels=g[g.type=='Duel']
                        rows.append({
                            'Player':player,
                            'Team':g.team.mode().iloc[0] if not g.team.mode().empty else '',
                            'Matches in sample':int(g.match_id.nunique()),
                            'Events':len(g),
                            'Shots':len(shots),
                            'Goals':int(shots.shot_outcome.eq('Goal').sum()),
                            'xG':round(shots.shot_xg.sum(),3) if shots.shot_xg.notna().any() else 0.0,
                            'Passes':len(passes),
                            'Completed passes':int(passes.successful_pass.sum()),
                            'Pass completion %':round(100*passes.successful_pass.mean(),1) if len(passes) else None,
                            'Carries':len(carries),
                            'Carry distance':round(carries.carry_distance.sum(),1) if len(carries) else 0.0,
                            'Pressures':int(g.type.eq('Pressure').sum()),
                            'Interceptions':int(g.type.eq('Interception').sum()),
                            'Recoveries':int(g.type.eq('Ball Recovery').sum()),
                            'Clearances':int(g.type.eq('Clearance').sum()),
                            'Blocks':int(g.type.eq('Block').sum()),
                            'Duels':len(duels),
                            'Under pressure events':int(g.under_pressure.sum())
                        })
                    summary=pd.DataFrame(rows).sort_values(['Matches in sample','Events'],ascending=False)
                    st.success(f"Učitano {len(chosen_ids)-len(errors)} utakmica · {len(data):,} događaja · {len(summary)} igrača")
                    st.warning('Ovaj modul prikazuje zbirne vrednosti u izabranom uzorku. Ne prikazuje per-90 ni percentile jer se stvarni minuti i uporediva populacija ne mogu pouzdano izvesti samo iz ovog prikaza događaja.')
                    tab1,tab2,tab3,tab4=st.tabs(['📋 Player database','⚖️ Compare players','📈 Metric explorer','⬇️ Export'])
                    with tab1:
                        search=st.text_input('Pretraga igrača ili kluba', key='sc_search').strip().lower()
                        filtered=summary
                        if search:
                            filtered=summary[summary.apply(lambda r: search in str(r['Player']).lower() or search in str(r['Team']).lower(),axis=1)]
                        st.dataframe(filtered,use_container_width=True,hide_index=True)
                        st.caption('Matches in sample označava broj izabranih utakmica u kojima igrač ima evidentirane događaje.')
                    with tab2:
                        candidate_players=sorted(summary.Player.tolist())
                        selected_players=st.multiselect('Izaberi do 10 igrača',candidate_players,default=candidate_players[:min(5,len(candidate_players))],max_selections=10,key='sc_compare')
                        compare_metrics=['xG','Shots','Goals','Passes','Completed passes','Pass completion %','Carries','Pressures','Interceptions','Recoveries','Clearances','Blocks','Duels']
                        cm=st.selectbox('Metrika za poređenje',compare_metrics,key='sc_metric')
                        comp_df=summary[summary.Player.isin(selected_players)].copy()
                        if not comp_df.empty:
                            comp_df['Per match in sample']=comp_df[cm]/comp_df['Matches in sample'].replace(0, pd.NA)
                            st.plotly_chart(px.bar(comp_df.sort_values('Per match in sample',ascending=False),x='Player',y='Per match in sample',color='Team',title=f'{cm} po utakmici u uzorku'),use_container_width=True)
                            st.dataframe(comp_df[['Player','Team','Matches in sample',cm,'Per match in sample']],use_container_width=True,hide_index=True)
                        else: st.info('Izaberi igrače za poređenje.')
                    with tab3:
                        metric=st.selectbox('Metrika',compare_metrics,key='sc_explore_metric')
                        top=summary.sort_values(metric,ascending=False).head(25)
                        st.plotly_chart(px.bar(top,x='Player',y=metric,color='Team',title=f'Top 25 · {metric}'),use_container_width=True)
                        st.caption('Grafikon prikazuje apsolutne vrednosti za izabrani uzorak, ne standardizovane percentile.')
                    with tab4:
                        st.download_button('Preuzmi player summary (CSV)',summary.to_csv(index=False).encode('utf-8'),file_name='scoutvision_statsbomb_player_summary.csv',mime='text/csv')
                        st.download_button('Preuzmi raw events (CSV)',data.to_csv(index=False).encode('utf-8'),file_name='scoutvision_statsbomb_events.csv',mime='text/csv')
                        st.caption('CSV fajlovi sadrže samo izabrane utakmice i dostupna polja iz javnog event feed-a.')
    except requests.RequestException:
        st.error('StatsBomb Open Data trenutno nije dostupan. Pokušaj ponovo kasnije.')
    except Exception as e:
        st.error('Greška u Player Scout & Compare modulu.')
        st.caption(str(e))

st.sidebar.divider()
st.sidebar.caption('Izvori: Open Matchday · API-Football Free (opcionalni ključ) · Hudl/StatsBomb Open Data. Proveri pokrivenost i uslove svakog izvora.')
