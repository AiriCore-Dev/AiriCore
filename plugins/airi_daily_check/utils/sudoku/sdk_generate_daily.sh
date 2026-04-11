CURRENT_DIR=$(cd $(dirname $0); pwd)
cd $CURRENT_DIR
touch tmp.txt
./sdk -n 1 -m 1 -u
cat game.txt >> tmp.txt
./sdk -n 1 -m 2 -u
cat game.txt >> tmp.txt
./sdk -n 1 -m 3 -u
cat game.txt >> tmp.txt
cat tmp.txt > game.txt
./sdk -s game.txt
rm tmp.txt