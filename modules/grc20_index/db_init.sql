CREATE TABLE public.grc20_block_hashes ( id bigserial NOT NULL,
																																									block_height int4 NOT NULL,
																																									block_hash text NOT NULL,
																																									CONSTRAINT grc20_block_hashes_pk PRIMARY KEY (id));


CREATE UNIQUE INDEX grc20_block_hashes_block_height_idx ON public.grc20_block_hashes USING btree (block_height);



CREATE TABLE public.grc20_events ( id bigserial NOT NULL,
																																			event_type int4 NOT NULL,
																																			block_height int4 NOT NULL,
																																			inscription_id text NOT NULL,
																																			"event" jsonb NOT NULL,
																																			CONSTRAINT grc20_events_pk PRIMARY KEY (id));


CREATE UNIQUE INDEX grc20_events_event_type_inscription_id_idx ON public.grc20_events USING btree (event_type, inscription_id);


CREATE INDEX grc20_events_block_height_idx ON public.grc20_events USING btree (block_height);


CREATE INDEX grc20_events_event_type_idx ON public.grc20_events USING btree (event_type);


CREATE INDEX grc20_events_inscription_id_idx ON public.grc20_events USING btree (inscription_id);


CREATE TABLE public.grc20_tickers ( id bigserial NOT NULL,
																																				tick text NOT NULL,
																																				code text NOT NULL,
																																				max_tick_supply numeric(40) NOT NULL,
																																				max_code_supply numeric(40) NOT NULL,
																																				decimals int4 NOT NULL,
																																				tick_remaining_supply numeric(40) NOT NULL,
																																				code_remaining_supply numeric(40) NOT NULL,
																																				block_height int4 NOT NULL,
																																				CONSTRAINT grc20_tickers_pk PRIMARY KEY (id));



CREATE UNIQUE INDEX grc20_tickers_tick_idx ON public.grc20_tickers USING btree (tick, code);
CREATE INDEX grc20_tickers_code_idx ON public.grc20_tickers USING btree (code);

CREATE TABLE public.grc20_collections (
	id bigserial NOT NULL,
	tick text NOT NULL,
	code text NOT NULL,
	inscription_id text NOT NULL,
	block_height int4 NOT NULL,
	CONSTRAINT grc20_collections_pk PRIMARY KEY (id)
);
CREATE INDEX grc20_collections_code_idx ON public.grc20_collections USING btree (code);
CREATE INDEX grc20_collections_tick_idx ON public.grc20_collections USING btree (tick);


CREATE TABLE public.grc20_cumulative_event_hashes ( id bigserial NOT NULL,
																																																				block_height int4 NOT NULL,
																																																				block_event_hash text NOT NULL,
																																																				cumulative_event_hash text NOT NULL,
																																																				CONSTRAINT grc20_cumulative_event_hashes_pk PRIMARY KEY (id));


CREATE UNIQUE INDEX grc20_cumulative_event_hashes_block_height_idx ON public.grc20_cumulative_event_hashes USING btree (block_height);


CREATE TABLE public.grc20_event_types ( id bigserial NOT NULL,
																																								event_type_name text NOT NULL,
																																								event_type_id int4 NOT NULL,
																																								CONSTRAINT grc20_event_types_pk PRIMARY KEY (id));


INSERT INTO public.grc20_event_types (event_type_name, event_type_id)
VALUES ('mint-inscribe',
									0);


CREATE TABLE public.grc20_indexer_version ( id bigserial NOT NULL,
																																												indexer_version text NOT NULL,
																																												db_version int4 NOT NULL,
																																												event_hash_version int4 NOT NULL,
																																												CONSTRAINT grc20_indexer_version_pk PRIMARY KEY (id));


INSERT INTO public.grc20_indexer_version (indexer_version, db_version, event_hash_version)
VALUES ('opi-grc20-full-node v0.4.0',
									4,
									2);

