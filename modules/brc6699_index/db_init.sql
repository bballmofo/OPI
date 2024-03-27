CREATE TABLE public.brc6699_block_hashes (
	id bigserial NOT NULL,
	block_height int4 NOT NULL,
	block_hash text NOT NULL,
	CONSTRAINT brc6699_block_hashes_pk PRIMARY KEY (id)
);
CREATE UNIQUE INDEX brc6699_block_hashes_block_height_idx ON public.brc6699_block_hashes USING btree (block_height);

CREATE TABLE public.brc6699_historic_balances (
	id bigserial NOT NULL,
	pkscript text NOT NULL,
	wallet text NULL,
	tick varchar(69) NOT NULL,
	overall_balance numeric(40) NOT NULL,
	available_balance numeric(40) NOT NULL,
	block_height int4 NOT NULL,
	event_id int8 NOT NULL,
	CONSTRAINT brc6699_historic_balances_pk PRIMARY KEY (id)
);
CREATE UNIQUE INDEX brc6699_historic_balances_event_id_idx ON public.brc6699_historic_balances USING btree (event_id);
CREATE INDEX brc6699_historic_balances_block_height_idx ON public.brc6699_historic_balances USING btree (block_height);
CREATE INDEX brc6699_historic_balances_pkscript_idx ON public.brc6699_historic_balances USING btree (pkscript);
CREATE INDEX brc6699_historic_balances_pkscript_tick_block_height_idx ON public.brc6699_historic_balances USING btree (pkscript, tick, block_height);
CREATE INDEX brc6699_historic_balances_tick_idx ON public.brc6699_historic_balances USING btree (tick);
CREATE INDEX brc6699_historic_balances_wallet_idx ON public.brc6699_historic_balances USING btree (wallet);

CREATE TABLE public.brc6699_events (
	id bigserial NOT NULL,
	tick varchar(69) NOT NULL,
	event_type int4 NOT NULL,
	block_height int4 NOT NULL,
	inscription_id text NOT NULL,
	"event" jsonb NOT NULL,
	CONSTRAINT brc6699_events_pk PRIMARY KEY (id)
);
CREATE UNIQUE INDEX brc6699_events_event_type_inscription_id_idx ON public.brc6699_events USING btree (event_type, inscription_id);
CREATE INDEX brc6699_events_tick_idx ON public.brc6699_events USING btree (tick);
CREATE INDEX brc6699_events_block_height_idx ON public.brc6699_events USING btree (block_height);
CREATE INDEX brc6699_events_event_type_idx ON public.brc6699_events USING btree (event_type);
CREATE INDEX brc6699_events_inscription_id_idx ON public.brc6699_events USING btree (inscription_id);

CREATE TABLE public.brc6699_collections (
	id bigserial NOT NULL,
	tick varchar(69) NOT NULL,
	inscription_id text NOT NULL,
	pkscript text NOT NULL,
	wallet text NULL,
	block_height int4 NOT NULL,
	CONSTRAINT brc6699_collections_pk PRIMARY KEY (id)
);
CREATE INDEX brc6699_collections_inscription_id_idx ON public.brc6699_collections USING btree (inscription_id);
CREATE INDEX brc6699_collections_block_height_idx ON public.brc6699_collections USING btree (block_height);
CREATE INDEX brc6699_collections_wallet_idx ON public.brc6699_collections USING btree (block_height);
CREATE INDEX brc6699_collections_tick_idx ON public.brc6699_collections USING btree (tick);

CREATE TABLE public.brc6699_tickers (
	id bigserial NOT NULL,
	tick varchar(69) NOT NULL,
	delegate_id text NOT NULL,
	inscription_id text NOT NULL,
	height int4 NULL,
	max_supply numeric(40) NULL,
	decimals int4 NOT NULL,
	limit_mint_count numeric(40) NULL,
	limit_mint_block numeric(40) NULL,
	remaining_supply numeric(40) NOT NULL,
	block_height int4 NOT NULL,
	CONSTRAINT brc6699_tickers_pk PRIMARY KEY (id)
);
CREATE UNIQUE INDEX brc6699_tickers_tick_idx ON public.brc6699_tickers USING btree (tick);

CREATE TABLE public.brc6699_cumulative_event_hashes (
	id bigserial NOT NULL,
	block_height int4 NOT NULL,
	block_event_hash text NOT NULL,
	cumulative_event_hash text NOT NULL,
	CONSTRAINT brc6699_cumulative_event_hashes_pk PRIMARY KEY (id)
);
CREATE UNIQUE INDEX brc6699_cumulative_event_hashes_block_height_idx ON public.brc6699_cumulative_event_hashes USING btree (block_height);

CREATE TABLE public.brc6699_event_types (
	id bigserial NOT NULL,
	event_type_name text NOT NULL,
	event_type_id int4 NOT NULL,
	CONSTRAINT brc6699_event_types_pk PRIMARY KEY (id)
);
INSERT INTO public.brc6699_event_types (event_type_name, event_type_id) VALUES ('deploy-inscribe', 0);
INSERT INTO public.brc6699_event_types (event_type_name, event_type_id) VALUES ('mint-inscribe', 1);
INSERT INTO public.brc6699_event_types (event_type_name, event_type_id) VALUES ('transfer-inscribe', 2);
INSERT INTO public.brc6699_event_types (event_type_name, event_type_id) VALUES ('transfer-transfer', 3);

CREATE TABLE public.brc6699_indexer_version (
	id bigserial NOT NULL,
	indexer_version text NOT NULL,
	db_version int4 NOT NULL,
	CONSTRAINT brc6699_indexer_version_pk PRIMARY KEY (id)
);
INSERT INTO public.brc6699_indexer_version (indexer_version, db_version) VALUES ('opi-brc6699-full-node v0.3.0', 3);

ALTER TABLE public.ord_content ADD COLUMN if not exists delegate_id text;