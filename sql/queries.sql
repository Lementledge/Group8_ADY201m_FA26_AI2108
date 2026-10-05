
    -- Query 1: Fatal accident rate by decade and weather condition (Answers RQ1)
    -- Technique: GROUP BY, Aggregation, Arithmetic Expressions
    SELECT 
        (ev_year / 10) * 10 AS decade,
        wx,
        COUNT(*) AS total_accidents,
        SUM(y) AS fatal_accidents,
        ROUND(AVG(y) * 100, 2) AS fatal_rate_pct
    FROM clean_events
    WHERE wx IN ('VMC', 'IMC')
    GROUP BY (ev_year / 10) * 10, wx
    ORDER BY decade ASC, wx DESC;
    


    -- Query 2: Aggregate aircraft features to event level (ev_id)
    -- Technique: CTE, Aggregate Functions (MAX, FIRST, COUNT)
    CREATE OR REPLACE TABLE ac_agg AS
    SELECT 
        ev_id,
        MAX(is_uas) AS is_uas,
        FIRST(far_part) AS far_part,
        FIRST(type_fly) AS type_fly,
        FIRST(flt_phase) AS flt_phase,
        MAX(num_eng) AS num_eng,
        COUNT(*) AS n_aircraft
    FROM clean_aircraft
    GROUP BY ev_id;
    
    SELECT is_uas, COUNT(*) AS n_events, AVG(num_eng) AS avg_engines
    FROM ac_agg
    GROUP BY is_uas;
    


    -- Query 3: Aggregate crew features (pilot flight hours and age) to ev_id
    -- Technique: Aggregate functions (MAX)
    CREATE OR REPLACE TABLE crew_agg AS
    SELECT 
        ev_id,
        MAX(crew_age) AS age_max,
        MAX(pilot_tot_hrs) AS hours_max
    FROM clean_crew
    GROUP BY ev_id;
    
    SELECT 
        ROUND(AVG(age_max), 1) AS avg_pilot_age,
        ROUND(AVG(hours_max), 1) AS avg_flight_hours,
        MIN(hours_max) AS min_hours,
        MAX(hours_max) AS max_hours
    FROM crew_agg;
    


    -- Query 4: Severity ranking across flight phases using Window Function
    -- Technique: Window Function RANK(), HAVING
    WITH phase_stats AS (
        SELECT 
            a.flt_phase,
            COUNT(*) AS n_events,
            ROUND(AVG(e.y) * 100, 2) AS fatal_rate_pct
        FROM clean_events e
        JOIN ac_agg a ON e.ev_id = a.ev_id
        WHERE a.is_uas = 0 AND a.flt_phase != 'UNK'
        GROUP BY a.flt_phase
        HAVING COUNT(*) > 500
    )
    SELECT 
        flt_phase,
        n_events,
        fatal_rate_pct,
        RANK() OVER (ORDER BY fatal_rate_pct DESC) AS severity_rank,
        ROUND(AVG(fatal_rate_pct) OVER (), 2) AS overall_avg_fatal_rate
    FROM phase_stats
    ORDER BY severity_rank ASC;
    


    -- Query 5: Year-over-year fatality rate trend using LAG() Window Function
    -- Technique: LAG(), OVER(ORDER BY ev_year)
    WITH yearly_summary AS (
        SELECT 
            ev_year,
            COUNT(*) AS total_accidents,
            ROUND(AVG(y) * 100, 2) AS fatal_rate_pct
        FROM clean_events
        GROUP BY ev_year
    )
    SELECT 
        ev_year,
        total_accidents,
        fatal_rate_pct,
        LAG(fatal_rate_pct, 1) OVER (ORDER BY ev_year) AS prev_year_fatal_rate,
        ROUND(fatal_rate_pct - LAG(fatal_rate_pct, 1) OVER (ORDER BY ev_year), 2) AS yoy_change_pct
    FROM yearly_summary
    ORDER BY ev_year DESC
    LIMIT 10;
    


    -- Query 6: Create consolidated feature table (feat) for machine learning
    -- Technique: INNER JOIN, LEFT JOIN
    CREATE OR REPLACE TABLE feat AS
    SELECT 
        e.ev_id,
        e.ev_year,
        e.ev_state,
        e.wx,
        e.light_cond,
        a.is_uas,
        a.far_part,
        a.type_fly,
        a.flt_phase,
        a.num_eng,
        a.n_aircraft,
        c.age_max,
        c.hours_max,
        e.y
    FROM clean_events e
    JOIN ac_agg a USING (ev_id)
    LEFT JOIN crew_agg c USING (ev_id);
    
    SELECT 
        is_uas,
        ev_year >= 2019 AS is_recent_test,
        COUNT(*) AS count_events,
        ROUND(AVG(y) * 100, 2) AS fatal_rate_pct
    FROM feat
    GROUP BY is_uas, ev_year >= 2019
    ORDER BY is_uas, is_recent_test;
    