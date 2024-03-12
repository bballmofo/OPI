#!/bin/bash

current_dir="$(pwd)"
echo $current_dir

#启动main_index
main_dir="$current_dir/main_index"
cd $main_dir
node index.js > ../main_index.log 2>&1 &

#启动brc20_index
brc20_dir="$current_dir/brc20_index"
cd $brc20_dir
python3 brc20_index.py > ../brc20_index.log 2>&1 &

#启动brc6699_index
brc6699_dir="$current_dir/brc6699_index"
cd $brc6699_dir
python3 brc6699_index.py > ../brc6699_index.log 2>&1 &

#启动bitmap_index
bitmap_dir="$current_dir/bitmap_index"
cd $bitmap_dir
python3 bitmap_index.py > ../bitmap_index.log 2>&1 &