from flask import Flask, render_template, request
from flask_restful import Resource, Api
from samplelist import methods, SampleContainer, SampleStatus, example_sample

app = Flask(__name__)
api = Api(app)

# master containers of sample lists (could also use status field)
# key can be either 'id' or 'name'

samples = SampleContainer()
samples.addSample(example_sample)

class GetListofSampleLists(Resource):
    def get(self):
        return {'sampleLists': [sample.toSampleList(entry=True) for sample in samples.samples if sample.status==SampleStatus.ACTIVE]}, 200

class GetSampleList(Resource):
    def get(self, sample_list_id):
        return {'sampleList': samples.getSample('id', sample_list_id, status=SampleStatus.ACTIVE).toSampleList()}, 200

class PutSampleListValidation(Resource):
    def post(self, sample_list_id):
        data = request.get_json(force=True)
        # TODO: some stuff, parse 'validationType' for SUCCESS or ERROR
        return {sample_list_id: data}, 200

class PutSampleData(Resource):
    def post(self, sample_list_id):
        data = request.get_json(force=True)
        # TODO: some stuff
        # Probable logic: once sample data is posted as successful, flag it as completed and move from sample_lists to completed_sample_lists
        return {sample_list_id: data}, 200

class RunSample(Resource):
    """Runs a sample """
    # TODO: Use POST to change status; might be useful for pausing, stopping; as coded this is best as a PUT
    def get(self, sample_name):
        sample = samples.getSample('name', sample_name)
        if sample is not None:
            sample.status = SampleStatus.ACTIVE
            return {}, 200
        else:
            return {}, 404

class GetSamples(Resource):
    """Gets list of sample names, IDs, and status"""
    def get(self):

        sample_list = []
        for sample in samples.samples:
            sample_list.append(dict({
                'id': sample.id,
                'name': sample.name,
                'status': sample.status
            }))

        return {'samples': sample_list}, 200

# LH URIs
api.add_resource(GetListofSampleLists, '/LH/GetListofSampleLists')
api.add_resource(GetSampleList, '/LH/GetSampleList/<sample_list_id>')
api.add_resource(PutSampleData, '/LH/PutSampleData/')
api.add_resource(PutSampleListValidation, '/LH/PutSampleListValidation/<sample_list_id>')

# Should these be LH endpoints, or NICE endpoints, or general API?
api.add_resource(RunSample, '/LH/RunSample/<sample_name>')
api.add_resource(GetSamples, '/LH/GetSamples/')

class GetLHMethods(Resource):
    def get(self):
        return methods, 200

# GUI URIs
api.add_resource(GetLHMethods, '/GUI/GetLHMethods/')

@app.route('/')
def root():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)