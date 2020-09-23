if __name__ == '__main__':
    json_file = open('Compound.json', 'w')
    json_file.write('{\n')
    with open('../../compound-liquidator-szhyg/src/constants/Compound.js', "r") as js_file:
        for counter, x in enumerate(js_file):
            if counter > 0 and not x.startswith('  //'):
                try:
                    if x[2] not in [' ', ']']:
                        n = 2
                        current_symbol = x[n]
                        word = ''
                        while current_symbol != ' ':
                            word = word + current_symbol
                            n += 1
                            current_symbol = x[n]
                        y = '  "' + word + '"' + x[n:]
                    else:
                        y = x
                except:
                    y = x
                json_file.write(y)
    json_file.close()